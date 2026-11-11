"""Gera a camada BRONZE do data lake com dados sintéticos realistas.

Simula 2 anos de leituras horárias das 6 estações IoT (pluviômetro +
sensor ultrassônico de nível do córrego + temperatura), o registro de
ocorrências da Defesa Civil e relatos de cidadãos em texto livre.

Os dados brutos saem "sujos" de propósito (nulos, leituras com defeito,
duplicatas, IDs inconsistentes) para que a camada SILVER tenha trabalho
real de limpeza.

Uso:  python -m bigdata.gerar_dados
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta

import numpy as np

from bigdata.catalogo import BAIRROS, BRONZE, NIVEL_BASE_CM

SEMENTE = 42
INICIO = datetime(2024, 11, 1)
HORAS = 2 * 365 * 24  # 2 anos

# probabilidade diária de temporal e escala de intensidade (mm/h) por mês
CLIMA_MES = {
    1: (0.38, 14), 2: (0.34, 13), 3: (0.28, 12), 4: (0.14, 9), 5: (0.09, 7), 6: (0.05, 6),
    7: (0.04, 6), 8: (0.05, 6), 9: (0.10, 8), 10: (0.17, 10), 11: (0.24, 11), 12: (0.33, 13),
}


def _gerar_chuva_regional(rng: np.random.Generator) -> np.ndarray:
    """Chuva 'regional' por hora; cada bairro recebe uma fração dela."""
    chuva = np.zeros(HORAS)
    for dia in range(HORAS // 24):
        data = INICIO + timedelta(days=dia)
        prob, escala = CLIMA_MES[data.month]
        # garoa fraca
        if rng.random() < 0.12:
            h0 = dia * 24 + int(rng.integers(0, 24))
            dur = int(rng.integers(1, 6))
            chuva[h0:h0 + dur] += rng.uniform(0.2, 2.0, size=len(chuva[h0:h0 + dur]))
        # temporal de verão, normalmente à tarde
        if rng.random() < prob:
            h0 = dia * 24 + int(rng.integers(13, 20))
            dur = int(rng.integers(1, 5))
            intens = rng.gamma(2.0, escala / 2, size=dur)
            intens[0] *= 1.4  # pico no início
            chuva[h0:h0 + dur] += intens[: len(chuva[h0:h0 + dur])]
    return chuva


def _simular_bairro(rng, chuva_regional, cfg):
    fator = rng.uniform(0.75, 1.25, size=HORAS)  # variação espacial da chuva
    chuva = np.round(np.clip(chuva_regional * fator, 0, None), 1)
    nivel = np.zeros(HORAS)
    temp = np.zeros(HORAS)
    atual = NIVEL_BASE_CM
    # hidrograma unitário: a água da bacia chega ao córrego com atraso de 1-3 h
    # (tempo de concentração). É essa janela que permite avisar antes.
    pesos = (0.15, 0.45, 0.45, 0.25)
    for t in range(HORAS):
        base = NIVEL_BASE_CM + rng.normal(0, 2)
        escoamento = sum(w * chuva[t - k] for k, w in enumerate(pesos) if t - k >= 0)
        atual = base + (atual - base) * 0.78 + cfg["sensibilidade"] * escoamento
        nivel[t] = round(max(atual, 20), 1)
        data = INICIO + timedelta(hours=t)
        sazonal = 6 * np.cos((data.month - 1) / 12 * 2 * np.pi)
        diario = 4 * np.sin((data.hour - 9) / 24 * 2 * np.pi)
        temp[t] = round(22 + sazonal + diario - 0.15 * chuva[t] + rng.normal(0, 0.8), 1)
    return chuva, nivel, temp


def _sujar(rng, valor, tipo):
    """Insere defeitos típicos de sensores de campo."""
    r = rng.random()
    if r < 0.010:
        return None  # pacote perdido
    if r < 0.013:
        return {"nivel": 999.0, "chuva": -5.0, "temp": -99.0}[tipo]  # leitura inválida
    return float(valor)


def gerar() -> dict:
    rng = np.random.default_rng(SEMENTE)
    random.seed(SEMENTE)
    BRONZE.mkdir(parents=True, exist_ok=True)
    chuva_regional = _gerar_chuva_regional(rng)

    leituras_path = BRONZE / "leituras_iot.jsonl"
    ocorrencias = []
    n_linhas = 0
    with leituras_path.open("w", encoding="utf-8") as f:
        for bairro, cfg in BAIRROS.items():
            chuva, nivel, temp = _simular_bairro(rng, chuva_regional, cfg)
            em_evento = False
            for t in range(HORAS):
                ts = INICIO + timedelta(hours=t, minutes=int(rng.integers(0, 3)))
                device = cfg["estacao"] if rng.random() > 0.02 else cfg["estacao"].lower()
                registro = {
                    "device_id": device,
                    "ts": ts.isoformat(),
                    "payload": {
                        "chuva_mm": _sujar(rng, chuva[t], "chuva"),
                        "nivel_cm": _sujar(rng, nivel[t], "nivel"),
                        "temp_c": _sujar(rng, temp[t], "temp"),
                    },
                    "fw": "1.2.0",
                }
                linha = json.dumps(registro, ensure_ascii=False)
                f.write(linha + "\n")
                n_linhas += 1
                if rng.random() < 0.005:  # reenvio duplicado (retry do dispositivo)
                    f.write(linha + "\n")
                    n_linhas += 1
                # ocorrência da Defesa Civil: início de cada transbordamento
                acima = nivel[t] >= cfg["cota_cm"]
                if acima and not em_evento:
                    dur = 1
                    while t + dur < HORAS and nivel[t + dur] >= cfg["cota_cm"]:
                        dur += 1
                    ocorrencias.append({
                        "bairro": bairro,
                        "inicio": (INICIO + timedelta(hours=t)).isoformat(),
                        "duracao_h": dur,
                        "nivel_max_cm": float(nivel[t:t + dur].max()),
                        "familias_afetadas": int(rng.integers(5, 40) * (nivel[t:t + dur].max() / cfg["cota_cm"])),
                    })
                em_evento = acima

    with (BRONZE / "ocorrencias_defesa_civil.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ocorrencias[0].keys()))
        w.writeheader()
        w.writerows(ocorrencias)

    relatos = gerar_relatos(rng, ocorrencias)
    with (BRONZE / "relatos_cidadaos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(relatos[0].keys()))
        w.writeheader()
        w.writerows(relatos)

    resumo = {"leituras": n_linhas, "ocorrencias": len(ocorrencias), "relatos": len(relatos)}
    print(f"[bronze] gerado em {BRONZE}: {resumo}")
    return resumo


# ---------------------------------------------------------------------------
# Relatos de cidadãos (texto livre) — base de treino da triagem por IA
# ---------------------------------------------------------------------------
LOCAIS = ["na rua {r}", "perto da escola", "em frente ao posto de saúde", "na esquina da {r}",
          "na avenida {r}", "atrás do mercado", "na viela {r}", "no ponto de ônibus da {r}"]
RUAS = ["das Flores", "Sao Joao", "Amador Bueno", "Itaquera", "Tiradentes", "Bom Jesus",
        "do Córrego", "Santa Rita", "Paulo VI", "Brasil"]

MODELOS_RELATO = {
    ("alagamento", "alta"): [
        "água na altura da cintura {l}, tem gente ilhada dentro de casa",
        "a enchente invadiu as casas {l}, idosos precisando de ajuda",
        "carro sendo arrastado pela correnteza {l}",
        "córrego transbordou {l}, água entrando nas casas muito rápido",
        "família ilhada no segundo andar {l}, água subindo sem parar",
        "alagamento forte {l}, água no joelho e subindo, crianças em casa",
    ],
    ("alagamento", "media"): [
        "rua alagada {l}, carros não conseguem passar",
        "água acumulada {l} cobrindo a calçada inteira",
        "alagamento {l}, ônibus parado e pedestres sem conseguir atravessar",
        "a rua virou um rio {l}, água chegando no portão",
    ],
    ("alagamento", "baixa"): [
        "poça grande de água {l} depois da chuva",
        "um pouco de água empoçada {l}, dá pra passar com cuidado",
        "lâmina de água {l}, nada grave por enquanto",
    ],
    ("bueiro_entupido", "media"): [
        "bueiro entupido de lixo {l}, a água não escoa",
        "boca de lobo cheia de entulho {l}, vai alagar na próxima chuva",
        "galeria entupida {l}, água voltando pelo ralo",
    ],
    ("bueiro_entupido", "baixa"): [
        "bueiro com folhas {l}, precisa de limpeza",
        "grade do bueiro quebrada e com sujeira {l}",
        "tampa de bueiro com lixo acumulado {l}",
    ],
    ("deslizamento", "alta"): [
        "barranco desabou {l}, casa com risco de cair",
        "deslizamento de terra {l}, tem rachadura na parede das casas",
        "encosta cedendo {l}, moradores com medo, terra descendo",
    ],
    ("deslizamento", "media"): [
        "terra escorrendo do morro {l} com a chuva",
        "pequeno deslizamento {l}, lama na calçada",
    ],
    ("queda_arvore", "alta"): [
        "árvore caiu sobre a fiação {l}, fios soltando faísca",
        "árvore grande caiu em cima de um carro {l}, rua bloqueada",
    ],
    ("queda_arvore", "media"): [
        "galho grande caiu {l} e bloqueou metade da rua",
        "árvore tombada {l} impedindo a passagem",
    ],
    ("queda_arvore", "baixa"): [
        "árvore inclinada {l}, parece que pode cair",
        "galhos soltos na calçada {l}",
    ],
    ("outros", "baixa"): [
        "falta de iluminação {l}, fica escuro quando chove",
        "buraco na pista {l}",
        "lixo acumulado na calçada {l}",
        "semáforo apagado {l}",
    ],
}

PREFIXOS = ["", "urgente: ", "socorro ", "boa tarde, ", "gostaria de avisar que ", "olá, ", ""]
SUFIXOS = ["", "", ". por favor mandem ajuda", ". faz 1 hora", "!!!", ". obrigado", ". desde ontem"]


def _texto(rng, modelo):
    local = random.choice(LOCAIS).format(r=random.choice(RUAS))
    txt = random.choice(PREFIXOS) + modelo.format(l=local) + random.choice(SUFIXOS)
    if rng.random() < 0.3:
        txt = txt.lower()
    if rng.random() < 0.15:  # erros de digitação simples
        txt = txt.replace("ç", "c").replace("ã", "a").replace("á", "a")
    return txt


def gerar_relatos(rng, ocorrencias):
    relatos = []
    chaves = list(MODELOS_RELATO.keys())
    pesos = np.array([5 if c[0] == "alagamento" else 2 for c in chaves], dtype=float)
    pesos /= pesos.sum()
    bairros = list(BAIRROS.keys())
    for i in range(1800):
        # 60% dos relatos ocorrem em dias de alagamento real
        if ocorrencias and rng.random() < 0.6:
            oc = ocorrencias[int(rng.integers(0, len(ocorrencias)))]
            ts = datetime.fromisoformat(oc["inicio"]) + timedelta(minutes=int(rng.integers(0, 180)))
            bairro = oc["bairro"]
            chave = chaves[int(rng.choice(len(chaves), p=pesos))]
        else:
            ts = INICIO + timedelta(minutes=int(rng.integers(0, HORAS * 60)))
            bairro = random.choice(bairros)
            chave = random.choice([c for c in chaves if c[0] != "alagamento" or c[1] == "baixa"])
        cat, sev = chave
        relatos.append({
            "id": i + 1,
            "ts": ts.isoformat(timespec="minutes"),
            "bairro": bairro,
            "texto": _texto(rng, random.choice(MODELOS_RELATO[chave])),
            "categoria": cat,
            "severidade": sev,
        })
    return relatos


if __name__ == "__main__":
    gerar()
