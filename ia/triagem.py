"""Triagem automática de relatos de cidadãos.

Camada 1 (IA):     classificador TF-IDF + Regressão Logística -> categoria e severidade.
Camada 2 (regras): palavras-chave de risco à vida elevam a severidade para "alta",
                   mesmo que o modelo erre (segurança acima de tudo).
"""
from __future__ import annotations

import re
from functools import lru_cache

import joblib

from bigdata.catalogo import MODELOS
from bigdata.pipeline import normalizar_texto

# Regras de urgência (texto normalizado, sem acento). Qualquer ocorrência -> severidade alta.
PADROES_URGENCIA = [
    r"ilhad", r"arrastad", r"correnteza", r"cintura", r"\bpeito\b", r"invad\w* (as |a )?casa",
    r"desab", r"rachadura", r"faisca", r"fio\w* solt", r"risco de vida", r"pessoa presa",
    r"preso[as]? em casa", r"agua entrando", r"afogad",
]
_RE_URGENCIA = re.compile("|".join(PADROES_URGENCIA))

TEMPO_RESPOSTA = {"alta": "até 30 min", "media": "até 4 h", "baixa": "até 48 h"}
ORGAO = {
    "alagamento": "Defesa Civil",
    "deslizamento": "Defesa Civil",
    "bueiro_entupido": "Subprefeitura - Limpeza Urbana",
    "queda_arvore": "Subprefeitura - Manejo Arbóreo",
    "outros": "Central 156",
}


def aplicar_regras_urgencia(texto: str, severidade_modelo: str) -> str:
    return "alta" if _RE_URGENCIA.search(normalizar_texto(texto)) else severidade_modelo


@lru_cache(maxsize=1)
def _modelos():
    return joblib.load(MODELOS / "modelo_triagem.joblib")


def triar(texto: str) -> dict:
    m = _modelos()
    norm = normalizar_texto(texto)
    cat_proba = m["categoria"].predict_proba([norm])[0]
    idx = int(cat_proba.argmax())
    categoria = str(m["categoria"].classes_[idx])
    sev_modelo = str(m["severidade"].predict([norm])[0])
    severidade = aplicar_regras_urgencia(texto, sev_modelo)
    return {
        "categoria": categoria,
        "confianca": round(float(cat_proba[idx]), 2),
        "severidade": severidade,
        "regra_urgencia_aplicada": severidade != sev_modelo,
        "orgao_responsavel": ORGAO[categoria],
        "prazo_atendimento": TEMPO_RESPOSTA[severidade],
        "revisao_humana": bool(cat_proba[idx] < 0.6),  # baixa confiança -> fila de revisão
    }
