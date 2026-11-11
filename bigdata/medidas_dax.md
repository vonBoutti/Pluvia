# Medidas analíticas — Python (dashboard web) e DAX (Power BI)

O dashboard web calcula as medidas em `bigdata/analitico.py`. As mesmas medidas estão
abaixo em DAX, para quem quiser montar o painel no Power BI importando os CSVs da
camada gold (`bigdata/data/gold/diario_bairro.csv`, `relatos_categoria.csv`, `dim_bairro.csv`).

Modelo no Power BI: `diario_bairro[bairro]` → `dim_bairro[bairro]` (muitos-para-um) e uma
tabela `Calendario = CALENDARAUTO()` ligada a `diario_bairro[data]` e `relatos_categoria[data]`.
Filtros (segmentações): Bairro e intervalo de datas.

| Indicador | Python (`analitico.py`) | DAX |
|---|---|---|
| Chuva acumulada (mm) | `d["chuva_total_mm"].sum()` | `Chuva Acumulada = SUM(diario_bairro[chuva_total_mm])` |
| Alagamentos | `d["alagamentos"].sum()` | `Alagamentos = SUM(diario_bairro[alagamentos])` |
| Horas críticas | `d["horas_acima_cota"].sum()` | `Horas Criticas = SUM(diario_bairro[horas_acima_cota])` |
| Famílias afetadas | `d["familias_afetadas"].sum()` | `Familias Afetadas = SUM(diario_bairro[familias_afetadas])` |
| Índice de vulnerabilidade (alagamentos por 100 mm) | `indice_vulnerabilidade()` | `Indice Vulnerabilidade = DIVIDE([Alagamentos], [Chuva Acumulada]) * 100` |
| Dias com chuva forte (≥ 20 mm/h) | `nunique` de datas com `chuva_max_1h_mm >= 20` | `Dias Chuva Forte = CALCULATE(DISTINCTCOUNT(diario_bairro[data]), diario_bairro[chuva_max_1h_mm] >= 20)` |
| % relatos graves | `alta / total * 100` | `Relatos Graves % = DIVIDE(CALCULATE(SUM(relatos_categoria[qtd]), relatos_categoria[severidade] = "alta"), SUM(relatos_categoria[qtd]))` |
| Média móvel 7 dias da chuva | `rolling(7).mean()` | `Chuva MM7 = AVERAGEX(DATESINPERIOD(Calendario[Date], MAX(Calendario[Date]), -7, DAY), CALCULATE(AVERAGE(diario_bairro[chuva_total_mm])))` |
| População em bairros afetados | soma de `populacao` dos bairros com alagamento | `Pop Afetada = SUMX(FILTER(dim_bairro, CALCULATE([Alagamentos]) > 0), dim_bairro[populacao])` |
| Ranking de bairros | `ranking_bairros()` ordenado pelo índice | `Rank Vulnerabilidade = RANKX(ALL(dim_bairro[bairro]), [Indice Vulnerabilidade], , DESC)` |
| Variação vs. mesmo período do ano anterior | — | `Alagamentos YoY % = DIVIDE([Alagamentos] - CALCULATE([Alagamentos], SAMEPERIODLASTYEAR(Calendario[Date])), CALCULATE([Alagamentos], SAMEPERIODLASTYEAR(Calendario[Date])))` |

## Que decisão o painel apoia

O gestor da subprefeitura escolhe **onde investir primeiro** em prevenção (limpeza de bueiros,
piscinão, jardins de chuva, cadastro de moradores no SMS). O índice de vulnerabilidade separa
"choveu muito" de "drena mal": um bairro com muitos alagamentos e pouca chuva é prioridade.
A função `recomendacao()` transforma o ranking em uma frase de ação exibida no topo do painel.
