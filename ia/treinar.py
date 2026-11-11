"""Treina e avalia os dois modelos de IA do Pluvia.

1. Previsão de alagamento (próximas 3 h) a partir dos sensores IoT
   -> RandomForest sobre features da camada silver.
   Comparado com a regra usada hoje ("régua": alarme quando o nível
   atinge 80% da cota de transbordamento).

2. Triagem automática de relatos de cidadãos (texto livre)
   -> TF-IDF + Regressão Logística para categoria e severidade.

Saídas em ia/modelos/: modelo_risco.joblib, modelo_triagem.joblib, metricas.json

Uso:  python -m ia.treinar
"""
from __future__ import annotations

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from bigdata.catalogo import MODELOS, RAIZ, SILVER
from bigdata.pipeline import normalizar_texto
from ia.features import FEATURES, candidato

REGRA_ATUAL_PCT = 0.8  # régua manual: alarme com 80% da cota


def _metricas(y, pred) -> dict:
    return {
        "precisao": round(precision_score(y, pred, zero_division=0), 3),
        "recall": round(recall_score(y, pred, zero_division=0), 3),
        "f1": round(f1_score(y, pred, zero_division=0), 3),
        "alarmes_emitidos_h": int(pred.sum()),
    }


def antecedencia_eventos(df: pd.DataFrame, alerta: np.ndarray, janela: int = 6) -> dict:
    """Métricas por EVENTO, que é o que importa para o cidadão.

    - antecedência: horas de alerta contínuo imediatamente antes do transbordamento
    - falso alarme: episódio de alerta (horas consecutivas) sem transbordamento
      durante ele ou nas 3 h seguintes
    """
    df = df.assign(alerta=alerta)
    antecedencias, falsos = [], 0
    for _, g in df.groupby("estacao"):
        g = g.sort_values("hora").reset_index(drop=True)
        alag, al = g["alagado"].to_numpy(), g["alerta"].to_numpy()
        inicios = np.flatnonzero((alag == 1) & (np.r_[0, alag[:-1]] == 0))
        for i in inicios:
            lead, j = 0, i - 1
            while j >= max(0, i - janela) and al[j] == 1:
                lead += 1
                j -= 1
            antecedencias.append(lead)
        ini_ep = np.flatnonzero((al == 1) & (np.r_[0, al[:-1]] == 0))
        for s in ini_ep:
            e = s
            while e + 1 < len(al) and al[e + 1] == 1:
                e += 1
            if alag[s:e + 4].sum() == 0:
                falsos += 1
    arr = np.array(antecedencias) if antecedencias else np.array([0])
    meses = max(1, (df["hora"].max() - df["hora"].min()).days / 30)
    return {
        "eventos": int(len(antecedencias)),
        "antecedencia_media_min": round(float(arr.mean()) * 60, 1),
        "eventos_avisados_1h_antes_pct": round(float((arr >= 1).mean()) * 100, 1),
        "falsos_alarmes_por_mes": round(falsos / meses, 1),
    }


def escolher_limiar(treino: pd.DataFrame) -> tuple[float, dict]:
    """Escolhe o limiar por validação cruzada no TREINO (folds por mês), maximizando F1.

    O período de teste nunca é usado nessa escolha.
    """
    from sklearn.model_selection import GroupKFold

    oof = np.zeros(len(treino))
    grupos = treino["hora"].dt.to_period("M").astype(str)
    for idx_tr, idx_va in GroupKFold(n_splits=4).split(treino, groups=grupos):
        m = _novo_modelo()
        m.fit(treino.iloc[idx_tr][FEATURES], treino.iloc[idx_tr]["alagamento_prox_3h"])
        oof[idx_va] = m.predict_proba(treino.iloc[idx_va][FEATURES])[:, 1]
    y = treino["alagamento_prox_3h"].to_numpy()
    grade = {round(t, 2): f1_score(y, (oof >= t).astype(int), zero_division=0) for t in np.arange(0.1, 0.71, 0.05)}
    melhor = max(grade, key=grade.get)
    return float(melhor), {str(k): round(v, 3) for k, v in grade.items()}


def _novo_modelo() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=150, max_depth=8, min_samples_leaf=5,
                                  random_state=42, n_jobs=-1)


def treinar_risco() -> dict:
    df = pd.read_parquet(SILVER / "leituras.parquet")
    df = df[df["alagado"] == 0]  # prever o FUTURO: só momentos ainda sem transbordamento
    # 1º ano treina, 2º ano testa: os dois períodos têm uma estação chuvosa inteira
    corte = df["hora"].min() + pd.DateOffset(months=12)
    treino, teste = df[df["hora"] < corte], df[df["hora"] >= corte]

    # a IA só é treinada nas horas "candidatas" (com chuva recente ou córrego alto)
    treino_c = treino[candidato(treino)]
    limiar, grade_f1 = escolher_limiar(treino_c)
    modelo = _novo_modelo()
    modelo.fit(treino_c[FEATURES], treino_c["alagamento_prox_3h"])
    modelo.set_params(n_jobs=1)  # na API a previsão é de 1 linha: paralelizar só atrasa
    joblib.dump({"modelo": modelo, "features": FEATURES, "limiar": limiar}, MODELOS / "modelo_risco.joblib")

    def prever_lote(d: pd.DataFrame) -> np.ndarray:
        p = np.zeros(len(d))
        m = candidato(d).to_numpy()
        if m.any():
            p[m] = modelo.predict_proba(d.loc[m, FEATURES])[:, 1]
        return p

    proba = prever_lote(teste)
    pred_ia = (proba >= limiar).astype(int)
    pred_regra = (teste["nivel_pct_cota"] >= REGRA_ATUAL_PCT).astype(int).to_numpy()
    y = teste["alagamento_prox_3h"].to_numpy()

    # antecedência medida na série completa do período de teste (inclui horas alagadas)
    completo = pd.read_parquet(SILVER / "leituras.parquet")
    completo = completo[completo["hora"] >= corte].reset_index(drop=True)
    p_full = prever_lote(completo)
    importancias = sorted(zip(FEATURES, modelo.feature_importances_, strict=True), key=lambda x: -x[1])

    return {
        "periodo_treino": f"{treino['hora'].min():%Y-%m-%d} a {treino['hora'].max():%Y-%m-%d}",
        "periodo_teste": f"{teste['hora'].min():%Y-%m-%d} a {teste['hora'].max():%Y-%m-%d}",
        "estacoes": int(df["estacao"].nunique()),
        "amostras_treino": int(len(treino)), "amostras_treino_candidatas": int(len(treino_c)),
        "amostras_teste": int(len(teste)),
        "positivos_teste": int(y.sum()),
        "limiar_alerta": limiar,
        "f1_validacao_cruzada_por_limiar": grade_f1,
        "ia": {**_metricas(y, pred_ia), **antecedencia_eventos(completo, (p_full >= limiar).astype(int))},
        "regra_atual_80pct_cota": {**_metricas(y, pred_regra),
                                   **antecedencia_eventos(completo, (completo["nivel_pct_cota"] >= REGRA_ATUAL_PCT).astype(int).to_numpy())},
        "importancia_features": {k: round(float(v), 3) for k, v in importancias},
    }


def _pipeline_texto(C: float = 4.0) -> Pipeline:
    return Pipeline([
        ("tfidf", FeatureUnion([
            ("palavras", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(C=C, max_iter=2000, class_weight="balanced")),
    ])


def treinar_triagem() -> dict:
    df = pd.read_csv(SILVER / "relatos.csv")
    X = df["texto_norm"]
    Xtr, Xte, ytr, yte = train_test_split(X, df[["categoria", "severidade"]], test_size=0.25,
                                          random_state=42, stratify=df["categoria"])
    cat, sev = _pipeline_texto(), _pipeline_texto()
    cat.fit(Xtr, ytr["categoria"])
    sev.fit(Xtr, ytr["severidade"])
    joblib.dump({"categoria": cat, "severidade": sev}, MODELOS / "modelo_triagem.joblib")

    # validação extra com frases escritas à mão, fora dos modelos de texto do gerador
    manual = pd.read_csv(RAIZ / "ia" / "casos_validacao_manual.csv")
    Xm = manual["texto"].map(normalizar_texto)

    from ia.triagem import aplicar_regras_urgencia  # regras de automação sobre a IA
    sev_m = [aplicar_regras_urgencia(t, s) for t, s in zip(manual["texto"], sev.predict(Xm), strict=True)]

    t0 = time.perf_counter()
    for _ in range(100):
        cat.predict(Xte[:1])
        sev.predict(Xte[:1])
    ms = (time.perf_counter() - t0) / 100 * 1000

    return {
        "amostras_treino": int(len(Xtr)), "amostras_teste": int(len(Xte)),
        "teste_sintetico": {
            "acuracia_categoria": round(accuracy_score(yte["categoria"], cat.predict(Xte)), 3),
            "f1_macro_categoria": round(f1_score(yte["categoria"], cat.predict(Xte), average="macro"), 3),
            "acuracia_severidade": round(accuracy_score(yte["severidade"], sev.predict(Xte)), 3),
        },
        "validacao_manual": {
            "frases": int(len(manual)),
            "acuracia_categoria": round(accuracy_score(manual["categoria"], cat.predict(Xm)), 3),
            "acuracia_severidade": round(accuracy_score(manual["severidade"], sev_m), 3),
        },
        "tempo_medio_triagem_ms": round(ms, 2),
        "tempo_triagem_manual_estimado_s": 120,
    }


def executar() -> dict:
    MODELOS.mkdir(parents=True, exist_ok=True)
    metricas = {"risco_alagamento": treinar_risco(), "triagem_relatos": treinar_triagem()}
    (MODELOS / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metricas, indent=2, ensure_ascii=False))
    return metricas


if __name__ == "__main__":
    executar()
