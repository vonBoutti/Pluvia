"""Funções analíticas (medidas) sobre a camada GOLD — alimentam o dashboard.

Cada função equivale a uma medida DAX documentada em bigdata/medidas_dax.md,
para quem preferir montar o mesmo painel no Power BI usando os CSVs da gold.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from bigdata.catalogo import BAIRROS, GOLD

LIMIAR_CHUVA_FORTE_MM_H = 20  # INMET/Defesa Civil: chuva forte a partir de ~20 mm/h


@lru_cache(maxsize=1)
def _gold():
    diario = pd.read_csv(GOLD / "diario_bairro.csv", parse_dates=["data"])
    relatos = pd.read_csv(GOLD / "relatos_categoria.csv", parse_dates=["data"])
    return diario, relatos


def periodo_disponivel() -> dict:
    d, _ = _gold()
    return {"inicio": f"{d['data'].min():%Y-%m-%d}", "fim": f"{d['data'].max():%Y-%m-%d}"}


def filtrar(df: pd.DataFrame, bairro: str | None, inicio: str | None, fim: str | None) -> pd.DataFrame:
    if bairro:
        df = df[df["bairro"] == bairro]
    if inicio:
        df = df[df["data"] >= pd.Timestamp(inicio)]
    if fim:
        df = df[df["data"] <= pd.Timestamp(fim)]
    return df


def indice_vulnerabilidade(alagamentos: float, chuva_mm: float) -> float:
    """Alagamentos a cada 100 mm de chuva — quanto MENOR, mais resiliente o bairro."""
    return round(alagamentos / chuva_mm * 100, 2) if chuva_mm else 0.0


def kpis(d: pd.DataFrame, r: pd.DataFrame) -> dict:
    chuva = float(d["chuva_total_mm"].sum())
    alag = int(d["alagamentos"].sum())
    total_rel = int(r["qtd"].sum())
    alta = int(r.loc[r["severidade"] == "alta", "qtd"].sum())
    pop_afetada = sum(BAIRROS[b]["populacao"] for b in d.loc[d["alagamentos"] > 0, "bairro"].unique())
    return {
        "chuva_acumulada_mm": round(chuva, 1),
        "alagamentos": alag,
        "horas_criticas": int(d["horas_acima_cota"].sum()),
        "familias_afetadas": int(d["familias_afetadas"].sum()),
        "indice_vulnerabilidade": indice_vulnerabilidade(alag, chuva),
        "dias_chuva_forte": int(d.loc[d["chuva_max_1h_mm"] >= LIMIAR_CHUVA_FORTE_MM_H, "data"].nunique()),
        "relatos": total_rel,
        "relatos_graves_pct": round(alta / total_rel * 100, 1) if total_rel else 0.0,
        "populacao_em_bairros_afetados": int(pop_afetada),
    }


def serie_mensal(d: pd.DataFrame) -> list[dict]:
    m = d.assign(mes=d["data"].dt.to_period("M").astype(str)).groupby("mes").agg(
        chuva_mm=("chuva_total_mm", "sum"), alagamentos=("alagamentos", "sum"),
        horas_criticas=("horas_acima_cota", "sum")).reset_index()
    m["chuva_mm"] = m["chuva_mm"].round(1)
    return m.to_dict(orient="records")


def serie_diaria_media_movel(d: pd.DataFrame, janela: int = 7) -> list[dict]:
    s = d.groupby("data")["chuva_total_mm"].mean()
    out = pd.DataFrame({"chuva_mm": s.round(1), "media_movel_7d": s.rolling(janela, min_periods=1).mean().round(1)})
    return [{"data": f"{i:%Y-%m-%d}", **row} for i, row in out.iterrows()]


def ranking_bairros(d: pd.DataFrame) -> list[dict]:
    g = d.groupby("bairro").agg(chuva_mm=("chuva_total_mm", "sum"), alagamentos=("alagamentos", "sum"),
                                horas_criticas=("horas_acima_cota", "sum"),
                                familias_afetadas=("familias_afetadas", "sum")).reset_index()
    g["indice_vulnerabilidade"] = [indice_vulnerabilidade(a, c) for a, c in zip(g["alagamentos"], g["chuva_mm"], strict=True)]
    g["chuva_mm"] = g["chuva_mm"].round(1)
    return g.sort_values(["indice_vulnerabilidade", "alagamentos"], ascending=False).to_dict(orient="records")


def relatos_por_categoria(r: pd.DataFrame) -> list[dict]:
    g = r.pivot_table(index="categoria", columns="severidade", values="qtd", aggfunc="sum", fill_value=0)
    for s in ("baixa", "media", "alta"):
        if s not in g:
            g[s] = 0
    g["total"] = g[["baixa", "media", "alta"]].sum(axis=1)
    return g.reset_index().sort_values("total", ascending=False)[["categoria", "baixa", "media", "alta", "total"]].to_dict(orient="records")


def recomendacao(ranking: list[dict]) -> str:
    """Transforma o indicador em decisão (para o gestor público)."""
    criticos = [b for b in ranking if b["alagamentos"] > 0]
    if not criticos:
        return "Nenhum alagamento no período filtrado. Manter rotina de limpeza preventiva."
    b = criticos[0]
    return (f"Priorizar {b['bairro']}: {b['alagamentos']} alagamentos e {b['horas_criticas']} h acima da cota "
            f"(índice {b['indice_vulnerabilidade']} por 100 mm). Sugestão: limpeza de bueiros antes do verão, "
            f"cadastro de moradores no alerta por SMS e estudo de piscinão/jardim de chuva.")


def painel(bairro: str | None = None, inicio: str | None = None, fim: str | None = None) -> dict:
    diario, relatos = _gold()
    d = filtrar(diario, bairro, inicio, fim)
    r = filtrar(relatos, bairro, inicio, fim)
    ranking = ranking_bairros(filtrar(diario, None, inicio, fim))
    return {
        "filtros": {"bairro": bairro, "inicio": inicio, "fim": fim, **{"disponivel": periodo_disponivel()}},
        "kpis": kpis(d, r),
        "mensal": serie_mensal(d),
        "diario": serie_diaria_media_movel(d),
        "ranking_bairros": ranking,
        "relatos_categoria": relatos_por_categoria(r),
        "recomendacao": recomendacao(ranking if not bairro else [x for x in ranking if x["bairro"] == bairro]),
    }
