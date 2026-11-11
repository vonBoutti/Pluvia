"""Cálculo de features em tempo real (API) — mesma lógica da camada silver.

A estação IoT envia uma leitura consolidada por hora. A API guarda o
histórico e, a cada nova leitura, monta o vetor de features a partir das
últimas 24 leituras daquela estação.
"""
from __future__ import annotations

from typing import Sequence

# Apenas variáveis físicas medidas pelos sensores. Hora do dia e mês foram
# testados e descartados: o modelo "decorava" o horário dos temporais.
FEATURES = ["chuva_mm", "chuva_3h", "chuva_24h", "nivel_cm", "delta_nivel_1h", "nivel_pct_cota"]


def candidato(f):
    """Só vale rodar a IA se choveu nas últimas 24 h ou o córrego já passou de 50% do limite.

    Sem chuva e com córrego baixo, o risco nas próximas 3 h é zero por definição.
    Funciona com dict (API) ou DataFrame (treino).
    """
    return (f["chuva_24h"] > 0) | (f["nivel_pct_cota"] >= 0.5)


def montar_features(historico: Sequence[dict], cota_cm: float) -> dict:
    """`historico` em ordem cronológica; o último item é a leitura atual.

    Cada item precisa de `chuva_mm` e `nivel_cm`.
    """
    if not historico:
        raise ValueError("histórico vazio")
    atual = historico[-1]
    chuvas = [h["chuva_mm"] or 0.0 for h in historico]
    anterior = historico[-2]["nivel_cm"] if len(historico) > 1 else atual["nivel_cm"]
    return {
        "chuva_mm": float(atual["chuva_mm"] or 0.0),
        "chuva_3h": round(sum(chuvas[-3:]), 1),
        "chuva_24h": round(sum(chuvas[-24:]), 1),
        "nivel_cm": float(atual["nivel_cm"]),
        "delta_nivel_1h": round(float(atual["nivel_cm"]) - float(anterior), 1),
        "nivel_pct_cota": round(float(atual["nivel_cm"]) / cota_cm, 3),
    }
