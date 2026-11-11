"""Gera a camada BRONZE do data lake com dados sintéticos realistas.

Simula 2 anos de leituras horárias das 96 estações IoT (uma por distrito de
São Paulo): pluviômetro, sensor ultrassônico de nível do córrego e temperatura.
Gera também as ocorrências da Defesa Civil e relatos de cidadãos em texto livre.

A chuva é correlacionada por REGIÃO (células de tempestade): no mesmo dia a
Zona Leste pode ter temporal enquanto a Oeste fica seca.

Os dados brutos saem "sujos" de propósito (nulos, leituras com defeito,
duplicatas, IDs inconsistentes) para a camada SILVER ter trabalho real.
Saída comprimida (gzip), porque são ~1,7 milhão de leituras.

Uso:  python -m bigdata.gerar_dados
"""
from __future__ import annotations

import csv
import gzip
import random
from datetime import datetime, timedelta

import numpy as np
from scipy.signal import lfilter

from bigdata.catalogo import BAIRROS, BRONZE, NIVEL_BASE_CM, REGIOES

SEMENTE = 42
INICIO = datetime(2024, 11, 1)
HORAS = 2 * 365 * 24  # 2 anos
DIAS = HORAS // 24

# probabilidade diária de temporal e escala de intensidade (mm/h) por mês
CLIMA_MES = {
    1: (0.38, 14), 2: (0.34, 13), 3: (0.28, 12), 4: (0.14, 9), 5: (0.09, 7), 6: (0.05, 6),
    7: (0.04, 6), 8: (0.05, 6), 9: (0.10, 8), 10: (0.17, 10), 11: (0.24, 11), 12: (0.33, 13),
}
# hidrograma unitário: a água da bacia chega ao córrego com atraso de 1-3 h
# (tempo de concentração). É essa janela que permite avisar antes.
PESOS_ESCOAMENTO = (0.15, 0.45, 0.45, 0.25)
RECESSAO = 0.78  # fração do excesso de água que continua no córrego na hora seguinte


def _gerar_chuva_base(rng: np.random.Generator) -> np.ndarray:
    """Chuva-base por hora (temporais de verão à tarde + garoas)."""
    chuva = np.zeros(HORAS)
    for dia in range(DIAS):
        data = INICIO + timedelta(days=dia)
        prob, escala = CLIMA_MES[data.month]
        if rng.random() < 0.12:  # garoa fraca
            h0 = dia * 24 + int(rng.integers(0, 24))
            dur = int(rng.integers(1, 6))
            chuva[h0:h0 + dur] += rng.uniform(0.2, 2.0, size=len(chuva[h0:h0 + dur]))
        if rng.random() < prob:  # temporal de verão, normalmente à tarde
            h0 = dia * 24 + int(rng.integers(13, 20))
            dur = int(rng.integers(1, 5))
            intens = rng.gamma(2.0, escala / 2, size=dur)
            intens[0] *= 1.4  # pico no início
            chuva[h0:h0 + dur] += intens[: len(chuva[h0:h0 + dur])]
    return chuva


def simular(rng: np.random.Generator) -> dict:
    """Física das 96 estações de uma vez (matrizes estação x hora), sem laço hora a hora."""
    nomes = list(BAIRROS)
    n = len(nomes)
    base = _gerar_chuva_base(rng)
    # fator por região e por dia (célula de tempestade), repetido nas 24 h do dia
    fator_regiao = rng.uniform(0.35, 1.35, size=(len(REGIOES), DIAS)).repeat(24, axis=1)
    idx_regiao = np.array([REGIOES.index(BAIRROS[b]["regiao"]) for b in nomes])
    fator = fator_regiao[idx_regiao] * rng.uniform(0.8, 1.2, size=(n, HORAS))
    chuva = np.round(np.clip(base[None, :] * fator, 0, None), 1)

    sens = np.array([BAIRROS[b]["sensibilidade"] for b in nomes])[:, None]
    escoamento = lfilter(PESOS_ESCOAMENTO, [1.0], chuva, axis=1)
    excesso = lfilter([1.0], [1.0, -RECESSAO], sens * escoamento, axis=1)
    nivel = np.round(np.maximum(NIVEL_BASE_CM + excesso + rng.normal(0, 2, size=(n, HORAS)), 20), 1)

    horas = [INICIO + timedelta(hours=t) for t in range(HORAS)]
    meses = np.array([h.month for h in horas])
    hora_dia = np.array([h.hour for h in horas])
    sazonal = 6 * np.cos((meses - 1) / 12 * 2 * np.pi)
    diario = 4 * np.sin((hora_dia - 9) / 24 * 2 * np.pi)
    temp = np.round(22 + sazonal + diario - 0.15 * chuva + rng.normal(0, 0.8, size=(n, HORAS)), 1)
    return {"nomes": nomes, "chuva": chuva, "nivel": nivel, "temp": temp, "horas": horas}


def _sujar(rng, matriz: np.ndarray, invalido: float) -> list:
    """Defeitos típicos de sensores de campo: 1% pacote perdido (null), 0,3% leitura inválida."""
    r = rng.random(matriz.shape)
    txt = np.char.mod("%.1f", matriz).astype(object)
    txt[r < 0.013] = repr(invalido)
    txt[r < 0.010] = "null"
    return txt


def gerar() -> dict:
    rng = np.random.default_rng(SEMENTE)
    random.seed(SEMENTE)
    BRONZE.mkdir(parents=True, exist_ok=True)
    sim = simular(rng)
    nomes, chuva, nivel, temp, horas = sim["nomes"], sim["chuva"], sim["nivel"], sim["temp"], sim["horas"]

    chuva_s, nivel_s, temp_s = _sujar(rng, chuva, -5.0), _sujar(rng, nivel, 999.0), _sujar(rng, temp, -99.0)
    atraso = rng.integers(0, 3, size=chuva.shape)   # minutos de atraso do relógio
    minusculo = (rng.random(chuva.shape) < 0.02).astype(int)  # firmware antigo manda id minúsculo
    duplicado = rng.random(chuva.shape) < 0.005       # reenvio (retry do dispositivo)
    ts_txt = [h.strftime("%Y-%m-%dT%H:") for h in horas]

    n_linhas = 0
    with gzip.open(BRONZE / "leituras_iot.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as f:
        for i, nome in enumerate(nomes):
            est = BAIRROS[nome]["estacao"]
            ids = (est, est.lower())
            linhas = []
            for t in range(HORAS):
                linha = (f'{{"device_id": "{ids[minusculo[i, t]]}", "ts": "{ts_txt[t]}{atraso[i, t]:02d}:00", '
                         f'"payload": {{"chuva_mm": {chuva_s[i, t]}, "nivel_cm": {nivel_s[i, t]}, '
                         f'"temp_c": {temp_s[i, t]}}}, "fw": "1.2.0"}}')
                linhas.append(linha)
                if duplicado[i, t]:
                    linhas.append(linha)
            n_linhas += len(linhas)
            f.write("\n".join(linhas))
            f.write("\n")

    # ocorrência da Defesa Civil: início de cada transbordamento
    ocorrencias = []
    for i, nome in enumerate(nomes):
        cota = BAIRROS[nome]["cota_cm"]
        alag = nivel[i] >= cota
        for t in np.flatnonzero(alag & ~np.r_[False, alag[:-1]]):
            dur = 1
            while t + dur < HORAS and alag[t + dur]:
                dur += 1
            pico = float(nivel[i, t:t + dur].max())
            ocorrencias.append({
                "bairro": nome, "inicio": horas[t].isoformat(), "duracao_h": dur, "nivel_max_cm": pico,
                "familias_afetadas": int(rng.integers(5, 40) * (pico / cota)),
            })
    ocorrencias.sort(key=lambda o: o["inicio"])

    with (BRONZE / "ocorrencias_defesa_civil.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ocorrencias[0].keys()))
        w.writeheader()
        w.writerows(ocorrencias)

    relatos = gerar_relatos(rng, ocorrencias)
    with (BRONZE / "relatos_cidadaos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(relatos[0].keys()))
        w.writeheader()
        w.writerows(relatos)

    resumo = {"estacoes": len(nomes), "leituras": n_linhas, "ocorrencias": len(ocorrencias), "relatos": len(relatos)}
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
    for i in range(4000):
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
