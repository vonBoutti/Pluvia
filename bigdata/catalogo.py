"""Catálogo compartilhado: os 96 distritos de São Paulo, estações IoT e caminhos do data lake.

Cada distrito tem uma estação (AC-01 ... AC-96). A estação AC-01 fica no
Jardim Helena (onde está o Jardim Pantanal, região que alaga todo verão).

População: aproximada (Censo 2010), só para os indicadores.
Cota e sensibilidade: definidas pelo "perfil de risco" do distrito, ou seja,
se fica em várzea de rio/córrego (Tietê, Tamanduateí, Aricanduva, Pirajuçara...).
Todos os dados de sensores são SINTÉTICOS (bigdata/gerar_dados.py, semente fixa).
"""
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
DATA_LAKE = RAIZ / "bigdata" / "data"
BRONZE = DATA_LAKE / "bronze"
SILVER = DATA_LAKE / "silver"
GOLD = DATA_LAKE / "gold"
MODELOS = RAIZ / "ia" / "modelos"

# distrito: (região, população aproximada)
DISTRITOS = {
    # Leste
    "Jardim Helena": ("Leste", 135000), "Água Rasa": ("Leste", 84000), "Aricanduva": ("Leste", 89000),
    "Artur Alvim": ("Leste", 105000), "Belém": ("Leste", 45000), "Brás": ("Leste", 29000),
    "Cangaíba": ("Leste", 136000), "Carrão": ("Leste", 83000), "Cidade Líder": ("Leste", 126000),
    "Cidade Tiradentes": ("Leste", 211000), "Ermelino Matarazzo": ("Leste", 113000), "Guaianases": ("Leste", 103000),
    "Iguatemi": ("Leste", 127000), "Itaim Paulista": ("Leste", 224000), "Itaquera": ("Leste", 205000),
    "José Bonifácio": ("Leste", 124000), "Lajeado": ("Leste", 164000), "Mooca": ("Leste", 75000),
    "Pari": ("Leste", 17000), "Parque do Carmo": ("Leste", 68000), "Penha": ("Leste", 127000),
    "Ponte Rasa": ("Leste", 93000), "São Lucas": ("Leste", 142000), "São Mateus": ("Leste", 155000),
    "São Miguel": ("Leste", 92000), "São Rafael": ("Leste", 143000), "Sapopemba": ("Leste", 284000),
    "Tatuapé": ("Leste", 91000), "Vila Curuçá": ("Leste", 149000), "Vila Formosa": ("Leste", 94000),
    "Vila Jacuí": ("Leste", 142000), "Vila Matilde": ("Leste", 105000), "Vila Prudente": ("Leste", 104000),
    # Centro
    "Bela Vista": ("Centro", 69000), "Bom Retiro": ("Centro", 34000), "Cambuci": ("Centro", 37000),
    "Consolação": ("Centro", 57000), "Liberdade": ("Centro", 70000), "República": ("Centro", 57000),
    "Santa Cecília": ("Centro", 83000), "Sé": ("Centro", 24000),
    # Oeste
    "Alto de Pinheiros": ("Oeste", 43000), "Barra Funda": ("Oeste", 14000), "Butantã": ("Oeste", 54000),
    "Itaim Bibi": ("Oeste", 93000), "Jaguara": ("Oeste", 25000), "Jaguaré": ("Oeste", 50000),
    "Jardim Paulista": ("Oeste", 89000), "Lapa": ("Oeste", 66000), "Morumbi": ("Oeste", 46000),
    "Perdizes": ("Oeste", 111000), "Pinheiros": ("Oeste", 65000), "Raposo Tavares": ("Oeste", 100000),
    "Rio Pequeno": ("Oeste", 118000), "Vila Leopoldina": ("Oeste", 39000), "Vila Sônia": ("Oeste", 108000),
    # Norte
    "Anhanguera": ("Norte", 65000), "Brasilândia": ("Norte", 264000), "Cachoeirinha": ("Norte", 143000),
    "Casa Verde": ("Norte", 85000), "Freguesia do Ó": ("Norte", 142000), "Jaçanã": ("Norte", 94000),
    "Jaraguá": ("Norte", 184000), "Limão": ("Norte", 80000), "Mandaqui": ("Norte", 107000),
    "Perus": ("Norte", 80000), "Pirituba": ("Norte", 167000), "Santana": ("Norte", 118000),
    "São Domingos": ("Norte", 84000), "Tremembé": ("Norte", 197000), "Tucuruvi": ("Norte", 98000),
    "Vila Guilherme": ("Norte", 54000), "Vila Maria": ("Norte", 113000), "Vila Medeiros": ("Norte", 129000),
    # Sul
    "Campo Belo": ("Sul", 65000), "Campo Grande": ("Sul", 100000), "Campo Limpo": ("Sul", 211000),
    "Capão Redondo": ("Sul", 268000), "Cidade Ademar": ("Sul", 266000), "Cidade Dutra": ("Sul", 196000),
    "Cursino": ("Sul", 109000), "Grajaú": ("Sul", 360000), "Ipiranga": ("Sul", 106000),
    "Jabaquara": ("Sul", 223000), "Jardim Ângela": ("Sul", 295000), "Jardim São Luís": ("Sul", 267000),
    "Marsilac": ("Sul", 8000), "Moema": ("Sul", 83000), "Parelheiros": ("Sul", 139000),
    "Pedreira": ("Sul", 144000), "Sacomã": ("Sul", 247000), "Santo Amaro": ("Sul", 71000),
    "Saúde": ("Sul", 130000), "Socorro": ("Sul", 37000), "Vila Andrade": ("Sul", 127000),
    "Vila Mariana": ("Sul", 130000),
}

# Perfil de risco (várzeas e fundos de vale conhecidos por alagar)
RISCO_ALTO = {
    "Jardim Helena", "Itaim Paulista", "São Miguel", "Vila Curuçá", "Ermelino Matarazzo", "Cangaíba", "Penha",
    "Aricanduva", "Pari", "Brás", "Bom Retiro", "Barra Funda", "Lapa", "Vila Leopoldina", "Casa Verde", "Limão",
    "Vila Maria", "Vila Guilherme", "Ipiranga", "Sacomã", "Jardim São Luís", "Campo Limpo", "Rio Pequeno",
    "Jaguaré",
}
RISCO_MEDIO = {
    "Vila Jacuí", "Ponte Rasa", "Vila Prudente", "Mooca", "Tatuapé", "Belém", "Carrão", "Vila Formosa", "Cambuci",
    "Santa Cecília", "Jaguara", "Vila Medeiros", "Santana", "Freguesia do Ó", "Perus", "Pirituba", "Butantã",
    "Santo Amaro", "Capão Redondo", "Cidade Ademar", "Jabaquara", "Socorro", "Itaquera", "São Mateus",
    "Sapopemba", "Iguatemi", "Cursino", "Vila Andrade", "Pinheiros", "Itaim Bibi",
}
REGIOES = ["Centro", "Norte", "Sul", "Leste", "Oeste"]


def _montar_bairros() -> dict:
    rng = np.random.default_rng(2026)  # determinístico
    out = {}
    for i, (nome, (regiao, pop)) in enumerate(DISTRITOS.items(), start=1):
        if nome in RISCO_ALTO:
            perfil, sens, cota = "alto", 4.0 + rng.uniform(-0.2, 0.3), int(rng.integers(17, 22)) * 10
        elif nome in RISCO_MEDIO:
            perfil, sens, cota = "medio", 3.3 + rng.uniform(-0.25, 0.25), int(rng.integers(20, 25)) * 10
        else:
            perfil, sens, cota = "baixo", 2.5 + rng.uniform(-0.3, 0.3), int(rng.integers(23, 29)) * 10
        out[nome] = {"estacao": f"AC-{i:02d}", "regiao": regiao, "perfil": perfil,
                     "cota_cm": cota, "sensibilidade": round(float(sens), 2), "populacao": pop}
    # estação-vitrine da demonstração (mesma do sketch ESP32)
    out["Jardim Helena"].update({"cota_cm": 180, "sensibilidade": 4.3})
    return out


BAIRROS = _montar_bairros()
ESTACAO_PARA_BAIRRO = {v["estacao"]: k for k, v in BAIRROS.items()}

NIVEL_BASE_CM = 60
HORIZONTE_ALERTA_H = 3  # a IA prevê alagamento nas próximas 3 horas

CATEGORIAS_RELATO = ["alagamento", "bueiro_entupido", "deslizamento", "queda_arvore", "outros"]
SEVERIDADES = ["baixa", "media", "alta"]
