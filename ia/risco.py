"""Inferência do modelo de risco de alagamento e classificação em níveis."""
from __future__ import annotations

from functools import lru_cache

import joblib
import pandas as pd

from bigdata.catalogo import MODELOS
from ia.features import candidato


@lru_cache(maxsize=1)
def _carregar():
    return joblib.load(MODELOS / "modelo_risco.joblib")


# faixas de probabilidade -> nível de risco comunicado ao cidadão
def niveis(limiar_alerta: float) -> list[tuple[float, str, str]]:
    """O limiar de 'alerta' vem do treino (validação cruzada, ver metricas.json)."""
    return [
        (0.75, "emergencia", "Emergência"),
        (limiar_alerta, "alerta", "Alerta"),
        (round(limiar_alerta / 3, 3), "atencao", "Atenção"),
        (0.0, "normal", "Normal"),
    ]


def nivel_por_probabilidade(p: float, limiar_alerta: float = 0.4) -> tuple[str, str]:
    for limite, codigo, rotulo in niveis(limiar_alerta):
        if p >= limite:
            return codigo, rotulo
    return "normal", "Normal"


def prever(features: dict) -> dict:
    """Probabilidade de transbordamento nas próximas 3 h."""
    art = _carregar()
    if features["nivel_pct_cota"] >= 1.0:  # já transbordou: não precisa de previsão
        p = 1.0
    elif not candidato(features):  # tempo seco e córrego baixo: risco zero, sem gastar a IA
        p = 0.0
    else:
        X = pd.DataFrame([features])[art["features"]]
        p = float(art["modelo"].predict_proba(X)[0, 1])
    codigo, rotulo = nivel_por_probabilidade(p, art["limiar"])
    return {"probabilidade": round(p, 3), "nivel": codigo, "rotulo": rotulo}
