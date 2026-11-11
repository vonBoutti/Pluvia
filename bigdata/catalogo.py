"""Catálogo compartilhado: bairros monitorados, estações IoT e caminhos do data lake.

Os nomes de bairros são usados apenas como cenário. Todos os dados são
SINTÉTICOS, gerados por `bigdata/gerar_dados.py` com semente fixa.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA_LAKE = RAIZ / "bigdata" / "data"
BRONZE = DATA_LAKE / "bronze"
SILVER = DATA_LAKE / "silver"
GOLD = DATA_LAKE / "gold"
MODELOS = RAIZ / "ia" / "modelos"

# cota_cm: altura do córrego em que a água transborda para a rua.
# sensibilidade: quanto o nível sobe (cm) por mm de chuva — depende de
# impermeabilização, declividade e drenagem do bairro.
BAIRROS = {
    "Jardim Pantanal": {"estacao": "AC-01", "cota_cm": 180, "sensibilidade": 4.3, "populacao": 48000},
    "Vila Itaim": {"estacao": "AC-02", "cota_cm": 200, "sensibilidade": 4.05, "populacao": 31000},
    "Aricanduva": {"estacao": "AC-03", "cota_cm": 220, "sensibilidade": 3.9, "populacao": 89000},
    "Lapa de Baixo": {"estacao": "AC-04", "cota_cm": 210, "sensibilidade": 3.5, "populacao": 37000},
    "Ipiranga": {"estacao": "AC-05", "cota_cm": 240, "sensibilidade": 3.4, "populacao": 106000},
    "Pompeia": {"estacao": "AC-06", "cota_cm": 260, "sensibilidade": 2.7, "populacao": 41000},
}

ESTACAO_PARA_BAIRRO = {v["estacao"]: k for k, v in BAIRROS.items()}

NIVEL_BASE_CM = 60
HORIZONTE_ALERTA_H = 3  # a IA prevê alagamento nas próximas 3 horas

CATEGORIAS_RELATO = ["alagamento", "bueiro_entupido", "deslizamento", "queda_arvore", "outros"]
SEVERIDADES = ["baixa", "media", "alta"]
