"""Exporta modelos de IA e dados da camada gold para JSON, usados pela versão de demonstração (Vercel).

A IA roda no navegador com os MESMOS modelos treinados pelo projeto. Chamado por vercel/montar.py.
Saída: vercel/site/demo/*.json
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from bigdata.catalogo import BAIRROS, GOLD, MODELOS, RAIZ
from ia.automacao import ACOES_DEFESA_CIVIL, MENSAGENS
from ia.triagem import ORGAO, PADROES_URGENCIA, TEMPO_RESPOSTA

SAIDA = RAIZ / "vercel" / "site" / "demo"


def _salvar(nome: str, dados) -> None:
    caminho = SAIDA / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {nome}: {caminho.stat().st_size / 1024:.0f} KB")


def exportar_risco() -> None:
    art = joblib.load(MODELOS / "modelo_risco.joblib")
    arvores = []
    for est in art["modelo"].estimators_:
        t = est.tree_
        v = t.value[:, 0, :]
        p1 = (v[:, 1] / v.sum(axis=1)).round(5)
        arvores.append({
            "f": t.feature.tolist(), "t": np.round(t.threshold, 6).tolist(),
            "l": t.children_left.tolist(), "r": t.children_right.tolist(), "p": p1.tolist(),
        })
    _salvar("risco.json", {"features": art["features"], "limiar": art["limiar"], "arvores": arvores})


def _vetorizador(v) -> dict:
    vocab = v.vocabulary_
    termos = [None] * len(vocab)
    for termo, i in vocab.items():
        termos[i] = termo
    return {"analyzer": v.analyzer, "ngram": list(v.ngram_range), "termos": termos,
            "idf": np.round(v.idf_, 5).tolist()}


def _pipeline_texto(p) -> dict:
    uniao, clf = p.named_steps["tfidf"], p.named_steps["clf"]
    vets = [_vetorizador(v) for _, v in uniao.transformer_list]
    coef = clf.coef_
    if coef.shape[0] == 1:  # binário: sklearn guarda só a classe positiva
        coef = np.vstack([-coef, coef])
    return {"vetorizadores": vets, "classes": clf.classes_.tolist(),
            "coef": np.round(coef.T, 5).tolist(), "intercept": np.round(clf.intercept_, 5).tolist(),
            "binario": clf.coef_.shape[0] == 1}


def exportar_triagem() -> None:
    m = joblib.load(MODELOS / "modelo_triagem.joblib")
    _salvar("triagem.json", {
        "categoria": _pipeline_texto(m["categoria"]), "severidade": _pipeline_texto(m["severidade"]),
        "urgencia": PADROES_URGENCIA, "orgao": ORGAO, "prazo": TEMPO_RESPOSTA,
    })


def exportar_gold() -> None:
    d = pd.read_csv(GOLD / "diario_bairro.csv", parse_dates=["data"])
    r = pd.read_csv(GOLD / "relatos_categoria.csv", parse_dates=["data"])
    nomes = list(BAIRROS)
    idx = {b: i for i, b in enumerate(nomes)}
    inicio = d["data"].min()
    dias = int((d["data"].max() - inicio).days) + 1
    d["di"] = (d["data"] - inicio).dt.days
    chuva = np.zeros((len(nomes), dias))
    chmax = np.zeros((len(nomes), dias))
    for row in d.itertuples():
        chuva[idx[row.bairro], row.di] = row.chuva_total_mm
        chmax[idx[row.bairro], row.di] = row.chuva_max_1h_mm
    eventos = [[idx[x.bairro], int(x.di), int(x.alagamentos), int(x.horas_acima_cota), int(x.familias_afetadas)]
               for x in d.itertuples() if x.alagamentos or x.horas_acima_cota or x.familias_afetadas]
    cats = sorted(r["categoria"].unique().tolist())
    sevs = ["baixa", "media", "alta"]
    relatos = [[int((x.data - inicio).days), idx[x.bairro], cats.index(x.categoria), sevs.index(x.severidade), int(x.qtd)]
               for x in r.itertuples()]
    _salvar("gold.json", {
        "inicio": f"{inicio:%Y-%m-%d}", "dias": dias, "bairros": nomes,
        "chuva": np.round(chuva, 1).tolist(), "chmax": np.round(chmax, 1).tolist(),
        "eventos": eventos, "categorias": cats, "severidades": sevs, "relatos": relatos,
    })


def exportar_catalogo() -> None:
    cat = [{"bairro": b, "regiao": c["regiao"], "estacao": c["estacao"], "cota_cm": c["cota_cm"],
            "populacao": c["populacao"], "sensibilidade": c["sensibilidade"]} for b, c in BAIRROS.items()]
    _salvar("catalogo.json", cat)
    _salvar("agente.json", {"mensagens": MENSAGENS, "acoes": ACOES_DEFESA_CIVIL})
    _salvar("metricas.json", json.loads((MODELOS / "metricas.json").read_text(encoding="utf-8")))


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    print(f"Exportando para {SAIDA}")
    exportar_catalogo()
    exportar_risco()
    exportar_triagem()
    exportar_gold()


if __name__ == "__main__":
    main()
