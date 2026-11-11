"""Pipeline do data lake: BRONZE (bruto) -> SILVER (limpo) -> GOLD (analítico).

bronze/  leituras_iot.jsonl, ocorrencias_defesa_civil.csv, relatos_cidadaos.csv
silver/  leituras.csv (horário, limpo, com features), ocorrencias.csv, relatos.csv
gold/    diario_bairro.csv, mensal_bairro.csv, dim_bairro.csv
         qualidade.json (relatório de qualidade de dados)

Uso:  python -m bigdata.pipeline
"""
from __future__ import annotations

import json
import unicodedata

import numpy as np
import pandas as pd

from bigdata.catalogo import BAIRROS, BRONZE, ESTACAO_PARA_BAIRRO, GOLD, HORIZONTE_ALERTA_H, SILVER

FAIXAS_VALIDAS = {"chuva_mm": (0, 200), "nivel_cm": (0, 600), "temp_c": (-10, 50)}


# ---------------------------------------------------------------- SILVER ----
def limpar_leituras(bruto: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Recebe o JSON bruto normalizado e devolve a série horária limpa."""
    q = {"linhas_bronze": int(len(bruto))}
    df = bruto.rename(columns={"payload.chuva_mm": "chuva_mm", "payload.nivel_cm": "nivel_cm",
                               "payload.temp_c": "temp_c"})
    df["estacao"] = df["device_id"].astype(str).str.strip().str.upper()
    desconhecidas = ~df["estacao"].isin(ESTACAO_PARA_BAIRRO)
    q["estacao_desconhecida"] = int(desconhecidas.sum())
    df = df[~desconhecidas].copy()

    df["hora"] = pd.to_datetime(df["ts"], errors="coerce").dt.floor("h")
    q["timestamp_invalido"] = int(df["hora"].isna().sum())
    df = df.dropna(subset=["hora"])

    antes = len(df)
    df = df.drop_duplicates(subset=["estacao", "hora"], keep="first")
    q["duplicatas_removidas"] = int(antes - len(df))

    for col, (lo, hi) in FAIXAS_VALIDAS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        invalidos = (df[col] < lo) | (df[col] > hi)
        q[f"{col}_fora_da_faixa"] = int(invalidos.sum())
        df.loc[invalidos, col] = np.nan
        q[f"{col}_nulos"] = int(df[col].isna().sum())

    partes = []
    for estacao, g in df.groupby("estacao"):
        g = g.set_index("hora").sort_index()
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="h"))
        g["estacao"] = estacao
        g["imputado"] = g[["chuva_mm", "nivel_cm", "temp_c"]].isna().any(axis=1)
        g["nivel_cm"] = g["nivel_cm"].interpolate(limit=3).round(1)
        g["temp_c"] = g["temp_c"].interpolate(limit=3).round(1)
        g["chuva_mm"] = g["chuva_mm"].fillna(0.0)
        partes.append(g)
    df = pd.concat(partes).rename_axis("hora").reset_index()
    q["horas_imputadas"] = int(df["imputado"].sum())
    df = df.dropna(subset=["nivel_cm"])

    df["bairro"] = df["estacao"].map(ESTACAO_PARA_BAIRRO)
    df["cota_cm"] = df["bairro"].map(lambda b: BAIRROS[b]["cota_cm"])
    df = adicionar_features(df)
    q["linhas_silver"] = int(len(df))
    cols = ["hora", "estacao", "bairro", "chuva_mm", "nivel_cm", "temp_c", "cota_cm", "imputado",
            "chuva_3h", "chuva_24h", "delta_nivel_1h", "nivel_pct_cota", "hora_dia", "mes",
            "alagado", "alagamento_prox_3h"]
    return df[cols], q


def adicionar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engenharia de atributos usada pela IA (calculada por estação)."""
    df = df.sort_values(["estacao", "hora"]).copy()
    g = df.groupby("estacao")
    df["chuva_3h"] = g["chuva_mm"].transform(lambda s: s.rolling(3, min_periods=1).sum()).round(1)
    df["chuva_24h"] = g["chuva_mm"].transform(lambda s: s.rolling(24, min_periods=1).sum()).round(1)
    df["delta_nivel_1h"] = g["nivel_cm"].diff().fillna(0).round(1)
    df["nivel_pct_cota"] = (df["nivel_cm"] / df["cota_cm"]).round(3)
    df["hora_dia"] = df["hora"].dt.hour
    df["mes"] = df["hora"].dt.month
    df["alagado"] = (df["nivel_cm"] >= df["cota_cm"]).astype(int)
    futuro = [g["alagado"].shift(-k) for k in range(1, HORIZONTE_ALERTA_H + 1)]
    df["alagamento_prox_3h"] = pd.concat(futuro, axis=1).max(axis=1).fillna(0).astype(int)
    return df


def normalizar_texto(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt).lower().strip())
    return "".join(c for c in txt if not unicodedata.combining(c))


def limpar_relatos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts", "texto"])
    df["texto_norm"] = df["texto"].map(normalizar_texto)
    df = df[df["bairro"].isin(BAIRROS)]
    return df.drop_duplicates(subset=["texto", "ts", "bairro"])


# ------------------------------------------------------------------ GOLD ----
def construir_gold(leituras: pd.DataFrame, ocorr: pd.DataFrame, relatos: pd.DataFrame) -> dict[str, pd.DataFrame]:
    lt = leituras.assign(data=leituras["hora"].dt.date)
    diario = lt.groupby(["data", "bairro"]).agg(
        chuva_total_mm=("chuva_mm", "sum"),
        chuva_max_1h_mm=("chuva_mm", "max"),
        nivel_max_cm=("nivel_cm", "max"),
        horas_acima_cota=("alagado", "sum"),
        horas_monitoradas=("hora", "count"),
    ).reset_index()

    oc = ocorr.assign(data=pd.to_datetime(ocorr["inicio"]).dt.date)
    oc_d = oc.groupby(["data", "bairro"]).agg(alagamentos=("inicio", "count"),
                                              familias_afetadas=("familias_afetadas", "sum")).reset_index()
    rl = relatos.assign(data=relatos["ts"].dt.date, alta=(relatos["severidade"] == "alta").astype(int))
    rl_d = rl.groupby(["data", "bairro"]).agg(relatos=("id", "count"), relatos_alta=("alta", "sum")).reset_index()

    diario = diario.merge(oc_d, on=["data", "bairro"], how="left").merge(rl_d, on=["data", "bairro"], how="left")
    for c in ["alagamentos", "familias_afetadas", "relatos", "relatos_alta"]:
        diario[c] = diario[c].fillna(0).astype(int)
    diario["chuva_total_mm"] = diario["chuva_total_mm"].round(1)
    diario["data"] = pd.to_datetime(diario["data"])

    mensal = diario.assign(mes=diario["data"].dt.to_period("M").astype(str)).groupby(["mes", "bairro"]).agg(
        chuva_total_mm=("chuva_total_mm", "sum"),
        alagamentos=("alagamentos", "sum"),
        horas_acima_cota=("horas_acima_cota", "sum"),
        familias_afetadas=("familias_afetadas", "sum"),
        relatos=("relatos", "sum"),
    ).reset_index()
    mensal["chuva_total_mm"] = mensal["chuva_total_mm"].round(1)

    dim = pd.DataFrame([{"bairro": b, **v} for b, v in BAIRROS.items()])
    relatos_cat = rl.groupby(["data", "bairro", "categoria", "severidade"]).size().rename("qtd").reset_index()
    relatos_cat["data"] = pd.to_datetime(relatos_cat["data"])
    return {"diario_bairro": diario, "mensal_bairro": mensal, "dim_bairro": dim, "relatos_categoria": relatos_cat}


def executar() -> dict:
    SILVER.mkdir(parents=True, exist_ok=True)
    GOLD.mkdir(parents=True, exist_ok=True)

    bruto = pd.json_normalize(pd.read_json(BRONZE / "leituras_iot.jsonl", lines=True, dtype=False)
                              .to_dict(orient="records"))
    leituras, qualidade = limpar_leituras(bruto)
    ocorr = pd.read_csv(BRONZE / "ocorrencias_defesa_civil.csv")
    relatos = limpar_relatos(pd.read_csv(BRONZE / "relatos_cidadaos.csv"))

    leituras.to_csv(SILVER / "leituras.csv", index=False)
    ocorr.to_csv(SILVER / "ocorrencias.csv", index=False)
    relatos.to_csv(SILVER / "relatos.csv", index=False)

    gold = construir_gold(leituras, ocorr, relatos)
    for nome, df in gold.items():
        df.to_csv(GOLD / f"{nome}.csv", index=False)

    qualidade["relatos_silver"] = int(len(relatos))
    qualidade["ocorrencias"] = int(len(ocorr))
    (GOLD / "qualidade.json").write_text(json.dumps(qualidade, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[silver/gold] qualidade:", json.dumps(qualidade, ensure_ascii=False))
    return qualidade


if __name__ == "__main__":
    executar()
