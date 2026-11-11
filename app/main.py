"""API do Alerta Cheia — FastAPI.

Rodar:  uvicorn app.main:app --reload     (documentação interativa em /docs)
"""
from __future__ import annotations

import json
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.schemas import AtualizarRelato, Leitura, Login, NovaInscricao, NovoRelato
from app.seguranca import (
    autenticar,
    criar_token,
    exigir_chave_dispositivo,
    exigir_token,
    hash_contato,
    limite_relatos,
    mascarar_telefone,
)
from bigdata import analitico
from bigdata.catalogo import BAIRROS, ESTACAO_PARA_BAIRRO, MODELOS, NIVEL_BASE_CM
from ia import automacao, risco, triagem
from ia.features import montar_features

VERSAO = "1.0.0"


# ------------------------------------------------------------ monitoramento --
class Monitor:
    def __init__(self):
        self.inicio = time.time()
        self.requisicoes = Counter()
        self.status = Counter()
        self.latencia_total_ms = 0.0
        self.total = 0

    def registrar(self, rota: str, status_code: int, ms: float):
        self.requisicoes[rota] += 1
        self.status[str(status_code)] += 1
        self.latencia_total_ms += ms
        self.total += 1


monitor = Monitor()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def semear_demo() -> None:
    """Popula 24 h de leituras calmas por estação, para o painel não abrir vazio."""
    with db.transacao() as con:
        if con.execute("SELECT COUNT(*) FROM leituras").fetchone()[0]:
            return
        agora = datetime.now().replace(minute=0, second=0, microsecond=0)
        for bairro, cfg in BAIRROS.items():
            for h in range(24, 0, -1):
                con.execute(
                    "INSERT INTO leituras (estacao,bairro,ts,chuva_mm,nivel_cm,temp_c,probabilidade,nivel_risco)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (cfg["estacao"], bairro, (agora - timedelta(hours=h)).isoformat(), 0.0,
                     NIVEL_BASE_CM + (h % 3), 22.0, 0.0, "normal"))


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    db.inicializar()
    if config.SEED_DEMO:
        semear_demo()
    yield


app = FastAPI(title="Alerta Cheia API", version=VERSAO, lifespan=ciclo_de_vida,
              description="CitizenTech: previsão de alagamentos com IoT + IA e alerta ao cidadão.")


@app.middleware("http")
async def middleware_seguranca_monitoramento(request: Request, call_next):
    t0 = time.perf_counter()
    resposta = await call_next(request)
    rota = request.scope.get("route").path if request.scope.get("route") else "static"
    monitor.registrar(f"{request.method} {rota}", resposta.status_code, (time.perf_counter() - t0) * 1000)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
    return resposta


# ------------------------------------------------------------------ saúde ----
@app.get("/api/health", tags=["monitoramento"])
def health():
    with db.transacao() as con:
        con.execute("SELECT 1")
    return {"status": "ok", "versao": VERSAO, "modelos": (MODELOS / "modelo_risco.joblib").exists()}


@app.get("/api/metricas", tags=["monitoramento"])
def metricas():
    with db.transacao() as con:
        leit = con.execute("SELECT COUNT(*) FROM leituras").fetchone()[0]
        ativos = con.execute("SELECT COUNT(*) FROM alertas WHERE ativo=1").fetchone()[0]
        relatos = con.execute("SELECT COUNT(*) FROM relatos").fetchone()[0]
    return {
        "uptime_s": round(time.time() - monitor.inicio),
        "requisicoes_total": monitor.total,
        "latencia_media_ms": round(monitor.latencia_total_ms / monitor.total, 2) if monitor.total else 0,
        "por_status": dict(monitor.status),
        "por_rota": dict(monitor.requisicoes.most_common(15)),
        "negocio": {"leituras": leit, "alertas_ativos": ativos, "relatos": relatos},
    }


@app.get("/metrics", tags=["monitoramento"], response_class=PlainTextResponse)
def metricas_prometheus():
    """Formato Prometheus, para coleta por Prometheus/Grafana."""
    m = metricas()
    linhas = [
        "# TYPE alerta_cheia_uptime_seconds gauge", f"alerta_cheia_uptime_seconds {m['uptime_s']}",
        "# TYPE alerta_cheia_requests_total counter", f"alerta_cheia_requests_total {m['requisicoes_total']}",
        "# TYPE alerta_cheia_latency_avg_ms gauge", f"alerta_cheia_latency_avg_ms {m['latencia_media_ms']}",
        "# TYPE alerta_cheia_alertas_ativos gauge", f"alerta_cheia_alertas_ativos {m['negocio']['alertas_ativos']}",
        "# TYPE alerta_cheia_leituras_total counter", f"alerta_cheia_leituras_total {m['negocio']['leituras']}",
    ]
    linhas += [f'alerta_cheia_http_status_total{{code="{k}"}} {v}' for k, v in m["por_status"].items()]
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------- auth ----
@app.post("/api/auth/login", tags=["autenticação"])
def login(dados: Login):
    if not autenticar(dados.usuario, dados.senha):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha inválidos")
    return {"access_token": criar_token(dados.usuario), "token_type": "bearer", "expira_em_min": config.TOKEN_MINUTOS}


# --------------------------------------------------------------- bairros -----
def _ultima_leitura(con, bairro: str):
    r = con.execute("SELECT * FROM leituras WHERE bairro=? ORDER BY id DESC LIMIT 1", (bairro,)).fetchone()
    return dict(r) if r else None


@app.get("/api/bairros", tags=["cidadão"])
def listar_bairros():
    out = []
    with db.transacao() as con:
        for bairro, cfg in BAIRROS.items():
            ult = _ultima_leitura(con, bairro)
            alerta = con.execute("SELECT nivel, mensagem, criado_em FROM alertas WHERE bairro=? AND ativo=1 "
                                 "ORDER BY id DESC LIMIT 1", (bairro,)).fetchone()
            out.append({
                "bairro": bairro, "estacao": cfg["estacao"], "cota_cm": cfg["cota_cm"],
                "ultima_leitura": ult,
                "nivel_pct_cota": round(ult["nivel_cm"] / cfg["cota_cm"] * 100, 1) if ult else None,
                "risco": {"nivel": ult["nivel_risco"], "probabilidade": ult["probabilidade"]} if ult else None,
                "alerta_ativo": dict(alerta) if alerta else None,
            })
    return out


@app.get("/api/bairros/{bairro}/historico", tags=["cidadão"])
def historico(bairro: str, limite: int = Query(24, ge=1, le=200)):
    if bairro not in BAIRROS:
        raise HTTPException(404, "Bairro não encontrado")
    with db.transacao() as con:
        rows = con.execute("SELECT ts, chuva_mm, nivel_cm, probabilidade, nivel_risco FROM leituras "
                           "WHERE bairro=? ORDER BY id DESC LIMIT ?", (bairro, limite)).fetchall()
    return {"bairro": bairro, "cota_cm": BAIRROS[bairro]["cota_cm"], "leituras": db.linhas(rows)[::-1]}


# --------------------------------------------------------------- IoT ---------
def _executar_agente(con, bairro: str, risco_atual: dict) -> dict:
    ativo = con.execute("SELECT id, nivel FROM alertas WHERE bairro=? AND ativo=1 ORDER BY id DESC LIMIT 1",
                        (bairro,)).fetchone()
    uma_hora = (datetime.now() - timedelta(hours=1)).isoformat()
    graves = con.execute("SELECT COUNT(*) FROM relatos WHERE bairro=? AND categoria='alagamento' "
                         "AND severidade='alta' AND criado_em>=?", (bairro, uma_hora)).fetchone()[0]
    decisao = automacao.decidir(bairro, risco_atual, ativo["nivel"] if ativo else None, graves)
    if decisao["acao"] == "criar":
        con.execute("UPDATE alertas SET ativo=0, encerrado_em=? WHERE bairro=? AND ativo=1", (_agora(), bairro))
        dest = con.execute("SELECT COUNT(*) FROM inscricoes WHERE bairro=?", (bairro,)).fetchone()[0]
        cur = con.execute(
            "INSERT INTO alertas (bairro,nivel,mensagem,acao_defesa_civil,motivo,probabilidade,criado_em,destinatarios)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (bairro, decisao["nivel"], decisao["mensagem"], decisao["acao_defesa_civil"], decisao["motivo"],
             risco_atual["probabilidade"], _agora(), dest))
        decisao["alerta_id"] = cur.lastrowid
        decisao["sms_enviados_simulados"] = dest
    elif decisao["acao"] == "encerrar":
        con.execute("UPDATE alertas SET ativo=0, encerrado_em=? WHERE bairro=? AND ativo=1", (_agora(), bairro))
    return decisao


@app.post("/api/leituras", tags=["IoT"], dependencies=[Depends(exigir_chave_dispositivo)],
          status_code=status.HTTP_201_CREATED)
def receber_leitura(leitura: Leitura):
    bairro = ESTACAO_PARA_BAIRRO[leitura.estacao]
    cfg = BAIRROS[bairro]
    ts = (leitura.ts or datetime.now()).isoformat(timespec="seconds")
    with db.transacao() as con:
        anteriores = db.linhas(con.execute("SELECT chuva_mm, nivel_cm FROM leituras WHERE estacao=? "
                                           "ORDER BY id DESC LIMIT 23", (leitura.estacao,)).fetchall())[::-1]
        feats = montar_features(anteriores + [{"chuva_mm": leitura.chuva_mm, "nivel_cm": leitura.nivel_cm}], cfg["cota_cm"])
        r = risco.prever(feats)
        con.execute("INSERT INTO leituras (estacao,bairro,ts,chuva_mm,nivel_cm,temp_c,probabilidade,nivel_risco)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (leitura.estacao, bairro, ts, leitura.chuva_mm, leitura.nivel_cm, leitura.temp_c, r["probabilidade"], r["nivel"]))
        decisao = _executar_agente(con, bairro, r)
    return {"bairro": bairro, "features": feats, "risco": r, "agente": decisao}


# --------------------------------------------------------------- alertas -----
@app.get("/api/alertas", tags=["cidadão"])
def listar_alertas(ativos: bool = False, limite: int = Query(30, ge=1, le=200)):
    # apenas fragmentos constantes são concatenados; valores vão como parâmetros
    sql = "SELECT * FROM alertas" + (" WHERE ativo=1" if ativos else "") + " ORDER BY id DESC LIMIT ?"  # noqa: S608
    with db.transacao() as con:
        return db.linhas(con.execute(sql, (limite,)).fetchall())


@app.post("/api/inscricoes", tags=["cidadão"], status_code=status.HTTP_201_CREATED)
def inscrever(dados: NovaInscricao):
    h = hash_contato(dados.telefone)
    mascara = mascarar_telefone(dados.telefone)
    with db.transacao() as con:
        con.execute("INSERT OR IGNORE INTO inscricoes (bairro, contato_hash, contato_mascarado, criado_em) "
                    "VALUES (?,?,?,?)", (dados.bairro, h, mascara, _agora()))
    return {"bairro": dados.bairro, "telefone": mascara,
            "mensagem": "Inscrição confirmada. Você receberá alertas por SMS. Seu número é guardado de forma protegida."}


# --------------------------------------------------------------- relatos -----
@app.post("/api/relatos", tags=["cidadão"], status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(limite_relatos)])
def novo_relato(dados: NovoRelato):
    t0 = time.perf_counter()
    tri = triagem.triar(dados.texto)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    with db.transacao() as con:
        cur = con.execute(
            "INSERT INTO relatos (bairro,texto,categoria,severidade,confianca,orgao,prazo,revisao_humana,"
            "regra_urgencia,criado_em) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (dados.bairro, dados.texto, tri["categoria"], tri["severidade"], tri["confianca"],
             tri["orgao_responsavel"], tri["prazo_atendimento"], int(tri["revisao_humana"]),
             int(tri["regra_urgencia_aplicada"]), _agora()))
        agente = None
        if tri["categoria"] == "alagamento" and tri["severidade"] == "alta":  # R4: sinal humano
            ult = _ultima_leitura(con, dados.bairro)
            r = {"nivel": ult["nivel_risco"], "probabilidade": ult["probabilidade"]} if ult else \
                {"nivel": "normal", "probabilidade": 0.0}
            agente = _executar_agente(con, dados.bairro, r)
    return {"id": cur.lastrowid, "triagem": tri, "tempo_triagem_ms": ms, "agente": agente}


@app.get("/api/relatos", tags=["defesa civil"])
def listar_relatos(usuario: str = Depends(exigir_token), status_: str | None = Query(None, alias="status")):
    sql, args = "SELECT * FROM relatos", []
    if status_:
        sql += " WHERE status=?"
        args.append(status_)
    sql += (" ORDER BY CASE severidade WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, id DESC LIMIT 200")
    with db.transacao() as con:
        return db.linhas(con.execute(sql, args).fetchall())


@app.patch("/api/relatos/{relato_id}", tags=["defesa civil"])
def atualizar_relato(relato_id: int, dados: AtualizarRelato, usuario: str = Depends(exigir_token)):
    with db.transacao() as con:
        cur = con.execute("UPDATE relatos SET status=? WHERE id=?", (dados.status, relato_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Relato não encontrado")
    return {"id": relato_id, "status": dados.status, "atualizado_por": usuario}


@app.post("/api/admin/reset", tags=["defesa civil"])
def reset_demo(usuario: str = Depends(exigir_token)):
    """Limpa leituras/alertas e repovoa o cenário calmo (para demonstrações)."""
    with db.transacao() as con:
        con.execute("DELETE FROM leituras")
        con.execute("DELETE FROM alertas")
    semear_demo()
    return {"ok": True}


# ------------------------------------------------------------ big data/IA ----
@app.get("/api/dashboard", tags=["big data"])
def dashboard(bairro: str | None = None, inicio: str | None = None, fim: str | None = None):
    if bairro and bairro not in BAIRROS:
        raise HTTPException(404, "Bairro não encontrado")
    try:
        return analitico.painel(bairro, inicio, fim)
    except ValueError as err:
        raise HTTPException(422, "Datas inválidas (use AAAA-MM-DD)") from err


@app.get("/api/ia/metricas", tags=["IA"])
def metricas_ia():
    caminho = MODELOS / "metricas.json"
    if not caminho.exists():
        raise HTTPException(503, "Modelos ainda não treinados")
    return json.loads(caminho.read_text(encoding="utf-8"))


@app.post("/api/ia/triagem", tags=["IA"])
def testar_triagem(dados: NovoRelato):
    """Demonstração da IA de triagem sem gravar o relato."""
    return triagem.triar(dados.texto)


@app.exception_handler(Exception)
async def erro_generico(_: Request, exc: Exception):
    # não vaza stack trace para o cliente
    return JSONResponse(status_code=500, content={"detail": "Erro interno"})


app.mount("/", StaticFiles(directory=config.RAIZ / "frontend", html=True), name="frontend")
