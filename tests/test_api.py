"""Casos de teste do plano de testes (docs/plano_de_testes.md). IDs CT-xx batem com o plano."""
import sqlite3

import pandas as pd

from app import config
from bigdata.pipeline import limpar_leituras
from ia.automacao import decidir
from tests.conftest import IOT

TEMPESTADE = [0, 0, 4, 12, 18, 16, 8, 3]


def test_ct01_health(cliente):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["modelos"] is True


def test_ct02_login_senha_errada(cliente):
    r = cliente.post("/api/auth/login", json={"usuario": "admin_teste", "senha": "errada-123"})
    assert r.status_code == 401


def test_ct03_rota_protegida_exige_token(cliente, auth):
    assert cliente.get("/api/relatos").status_code == 401
    assert cliente.get("/api/relatos", headers={"Authorization": "Bearer token.falso.qualquer"}).status_code == 401
    assert cliente.get("/api/relatos", headers=auth).status_code == 200


def test_ct04_leitura_sem_chave_iot_rejeitada(cliente):
    r = cliente.post("/api/leituras", json={"estacao": "AC-01", "chuva_mm": 1, "nivel_cm": 70})
    assert r.status_code == 401
    r = cliente.post("/api/leituras", json={"estacao": "AC-01", "chuva_mm": 1, "nivel_cm": 70},
                     headers={"X-API-Key": "chave-errada"})
    assert r.status_code == 401


def test_ct05_validacao_de_entrada_da_leitura(cliente):
    invalidas = [
        {"estacao": "AC-01", "chuva_mm": 1, "nivel_cm": 999},   # fora da faixa do sensor
        {"estacao": "AC-01", "chuva_mm": -3, "nivel_cm": 80},   # chuva negativa
        {"estacao": "XX-99", "chuva_mm": 1, "nivel_cm": 80},    # estação não cadastrada
    ]
    for corpo in invalidas:
        assert cliente.post("/api/leituras", json=corpo, headers=IOT).status_code == 422


def test_ct06_fluxo_tempestade_alerta_antes_de_transbordar(cliente, auth):
    """Fluxo ponta a ponta: sensores -> IA -> agente -> alerta, ANTES do córrego atingir a cota (180 cm)."""
    cliente.post("/api/admin/reset", headers=auth)
    import random

    from iot.simulador import Estacao
    random.seed(7)
    est = Estacao("Jardim Helena")
    primeiro_alerta = None
    for chuva in TEMPESTADE:
        leitura = est.passo(chuva)
        r = cliente.post("/api/leituras", json=leitura, headers=IOT).json()
        if r["agente"]["acao"] == "criar" and primeiro_alerta is None:
            primeiro_alerta = leitura
    assert primeiro_alerta is not None, "nenhum alerta emitido"
    assert primeiro_alerta["nivel_cm"] < 180, "alerta deveria sair antes do transbordamento"
    ativos = cliente.get("/api/alertas?ativos=true").json()
    assert any(a["bairro"] == "Jardim Helena" for a in ativos)


def test_ct07_triagem_ia_relato_grave(cliente):
    r = cliente.post("/api/relatos", json={"bairro": "Itaim Paulista",
                                           "texto": "A água invadiu as casas e tem uma família ilhada no telhado"})
    assert r.status_code == 201
    t = r.json()["triagem"]
    assert t["categoria"] == "alagamento" and t["severidade"] == "alta"
    assert t["orgao_responsavel"] == "Defesa Civil"


def test_ct08_relato_com_html_rejeitado(cliente):
    r = cliente.post("/api/relatos", json={"bairro": "Perdizes", "texto": "<script>alert('x')</script> rua alagada"})
    assert r.status_code == 422
    r = cliente.post("/api/relatos", json={"bairro": "Bairro Inexistente", "texto": "rua alagada perto da escola"})
    assert r.status_code == 422


def test_ct09_rate_limit_relatos(cliente):
    corpo = {"bairro": "Ipiranga", "texto": "bueiro entupido de lixo na esquina"}
    codigos = [cliente.post("/api/relatos", json=corpo).status_code for _ in range(6)]
    assert codigos[:5] == [201] * 5
    assert codigos[5] == 429


def test_ct10_lgpd_telefone_nao_salvo_em_claro(cliente):
    r = cliente.post("/api/inscricoes", json={"bairro": "Aricanduva", "telefone": "(11) 97777-4321", "aceite_lgpd": True})
    assert r.status_code == 201
    assert r.json()["telefone"] == "(11) *****-4321"
    con = sqlite3.connect(config.DB_PATH)
    dump = " ".join(str(v) for row in con.execute("SELECT * FROM inscricoes") for v in row)
    con.close()
    assert "977774321" not in dump and "97777-4321" not in dump
    sem_aceite = cliente.post("/api/inscricoes", json={"bairro": "Aricanduva", "telefone": "11977774321", "aceite_lgpd": False})
    assert sem_aceite.status_code == 422


def test_ct11_pipeline_limpa_dados_brutos():
    bruto = pd.DataFrame([
        {"device_id": "AC-01", "ts": "2025-01-01T10:01:00", "payload.chuva_mm": 2.0, "payload.nivel_cm": 70.0, "payload.temp_c": 25.0},
        {"device_id": "AC-01", "ts": "2025-01-01T10:01:00", "payload.chuva_mm": 2.0, "payload.nivel_cm": 70.0, "payload.temp_c": 25.0},  # duplicata
        {"device_id": "ac-01", "ts": "2025-01-01T11:00:00", "payload.chuva_mm": -5.0, "payload.nivel_cm": 999.0, "payload.temp_c": 24.0},  # defeito
        {"device_id": "AC-01", "ts": "2025-01-01T12:02:00", "payload.chuva_mm": 0.0, "payload.nivel_cm": 80.0, "payload.temp_c": 23.0},
        {"device_id": "ZZ-77", "ts": "2025-01-01T12:00:00", "payload.chuva_mm": 0.0, "payload.nivel_cm": 50.0, "payload.temp_c": 23.0},  # desconhecida
    ])
    limpo, q = limpar_leituras(bruto)
    assert q["duplicatas_removidas"] == 1 and q["estacao_desconhecida"] == 1
    assert q["nivel_cm_fora_da_faixa"] == 1 and q["chuva_mm_fora_da_faixa"] == 1
    assert len(limpo) == 3
    assert limpo.iloc[1]["nivel_cm"] == 75.0  # interpolado entre 70 e 80
    assert limpo["chuva_mm"].min() >= 0


def test_ct12_regras_do_agente():
    alto = {"nivel": "alerta", "probabilidade": 0.6}
    assert decidir("Perdizes", alto, None, 0)["acao"] == "criar"                     # R1
    assert decidir("Perdizes", alto, "alerta", 0)["acao"] == "manter"                # R2 sem spam
    assert decidir("Perdizes", {"nivel": "emergencia", "probabilidade": .9}, "alerta", 0)["acao"] == "criar"  # R3
    assert decidir("Perdizes", {"nivel": "normal", "probabilidade": .0}, None, 2)["acao"] == "criar"  # R4
    assert decidir("Perdizes", {"nivel": "normal", "probabilidade": .0}, "alerta", 0)["acao"] == "encerrar"  # R5
    assert len(decidir("Perdizes", alto, None, 0)["mensagem"]) <= 160               # R6 SMS


def test_ct13_dashboard_filtros(cliente):
    geral = cliente.get("/api/dashboard").json()
    filtrado = cliente.get("/api/dashboard?bairro=Perdizes&inicio=2025-01-01&fim=2025-03-31").json()
    assert len(geral["kpis"]) >= 3
    assert filtrado["kpis"]["chuva_acumulada_mm"] < geral["kpis"]["chuva_acumulada_mm"]
    assert all("2025-01" <= m["mes"] <= "2025-03" for m in filtrado["mensal"])
    assert cliente.get("/api/dashboard?bairro=Atlantida").status_code == 404


def test_ct14_cabecalhos_de_seguranca_e_monitoramento(cliente):
    r = cliente.get("/index.html")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    m = cliente.get("/metrics").text
    assert "pluvia_requests_total" in m
