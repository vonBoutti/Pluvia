"""Prepara tudo que a API precisa: dados (bronze/silver/gold) e modelos de IA.

Uso:  python -m scripts.preparar
"""
import time

from bigdata import gerar_dados, pipeline
from ia import treinar


def main() -> None:
    t0 = time.time()
    print("1/3 Gerando dados brutos (bronze)...")
    gerar_dados.gerar()
    print("2/3 Pipeline silver/gold...")
    pipeline.executar()
    print("3/3 Treinando modelos de IA...")
    treinar.executar()
    print(f"Pronto em {time.time() - t0:.0f}s. Suba a API com: uvicorn app.main:app --env-file .env")


if __name__ == "__main__":
    main()
