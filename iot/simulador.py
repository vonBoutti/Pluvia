"""Simulador (mock) das 6 estações IoT do Pluvia.

Cada estação tem 3 sensores: pluviômetro (chuva_mm), ultrassônico (nivel_cm) e
DHT22 (temp_c). O simulador envia as leituras para a API exatamente como o ESP32
faria (POST /api/leituras + X-API-Key). Cada ciclo representa 1 hora.

Cenários:
  calmo       tempo seco em todos os bairros
  tempestade  temporal sobre um distrito (padrão: Jardim Helena), chuva menor no resto da mesma região
  replay      reproduz o maior alagamento real do histórico (camada silver) do bairro

Exemplos:
  python -m iot.simulador --cenario tempestade --bairro "Jardim Helena"
  python -m iot.simulador --cenario replay --bairro "Itaim Paulista" --intervalo 1
"""
from __future__ import annotations

import argparse
import os
import random
import time

import requests

from bigdata.catalogo import BAIRROS, NIVEL_BASE_CM, SILVER

# mm/h — temporal de verão típico (pico de 18 mm/h, ~60 mm no total)
PERFIL_TEMPESTADE = [0, 0, 4, 12, 18, 16, 8, 3, 0, 0, 0, 0, 0, 0]
PESOS_ESCOAMENTO = (0.15, 0.45, 0.45, 0.25)  # mesmo hidrograma do gerador de dados


class Estacao:
    def __init__(self, bairro: str):
        self.bairro = bairro
        self.cfg = BAIRROS[bairro]
        self.nivel = NIVEL_BASE_CM + random.uniform(-2, 2)
        self.chuvas: list[float] = []

    def passo(self, chuva: float) -> dict:
        self.chuvas.append(chuva)
        escoamento = sum(w * self.chuvas[-1 - k] for k, w in enumerate(PESOS_ESCOAMENTO) if k < len(self.chuvas))
        base = NIVEL_BASE_CM + random.gauss(0, 1.5)
        self.nivel = max(20.0, base + (self.nivel - base) * 0.78 + self.cfg["sensibilidade"] * escoamento)
        return {"estacao": self.cfg["estacao"], "chuva_mm": round(chuva, 1), "nivel_cm": round(self.nivel, 1),
                "temp_c": round(23 - 0.15 * chuva + random.gauss(0, 0.5), 1)}


def _da_regiao(alvo: str) -> list[str]:
    """Temporais são locais: simulamos as estações da mesma região do distrito-alvo."""
    return [b for b, c in BAIRROS.items() if c["regiao"] == BAIRROS[alvo]["regiao"]]


def roteiro(cenario: str, alvo: str, passos: int) -> dict[str, list[dict]]:
    """Gera a sequência de leituras de cada estação."""
    if cenario == "replay":
        return _roteiro_replay(alvo)
    seq = {}
    for bairro in _da_regiao(alvo):
        est = Estacao(bairro)
        fator = 1.0 if bairro == alvo else random.uniform(0.2, 0.45)
        perfil = PERFIL_TEMPESTADE if cenario == "tempestade" else [0] * passos
        perfil = (perfil + [0] * passos)[:passos]
        ruido = (lambda: 1.0) if bairro == alvo else (lambda: random.uniform(0.9, 1.1))
        seq[bairro] = [est.passo(c * fator * ruido()) for c in perfil]
    return seq


def _roteiro_replay(alvo: str) -> dict[str, list[dict]]:
    import pandas as pd

    df = pd.read_parquet(SILVER / "leituras.parquet")
    g = df[df["bairro"] == alvo].reset_index(drop=True)
    pico = int(g["nivel_cm"].idxmax())
    janela_ini = max(0, pico - 8)
    hora_ini, hora_fim = g.at[janela_ini, "hora"], g.at[min(len(g) - 1, pico + 4), "hora"]
    print(f"Replay: maior evento de {alvo} em {g.at[pico, 'hora']:%d/%m/%Y %H:%M} "
          f"(nível máx. {g.at[pico, 'nivel_cm']} cm, cota {BAIRROS[alvo]['cota_cm']} cm)")
    seq = {}
    for bairro in _da_regiao(alvo):
        cfg = BAIRROS[bairro]
        j = df[(df["bairro"] == bairro) & (df["hora"] >= hora_ini) & (df["hora"] <= hora_fim)]
        seq[bairro] = [{"estacao": cfg["estacao"], "chuva_mm": float(r.chuva_mm), "nivel_cm": float(r.nivel_cm),
                        "temp_c": None if pd.isna(r.temp_c) else float(r.temp_c)} for r in j.itertuples()]
    return seq


def executar(api: str, chave: str, cenario: str, alvo: str, passos: int, intervalo: float) -> list[dict]:
    seq = roteiro(cenario, alvo, passos)
    n = min(len(v) for v in seq.values())
    respostas = []
    sessao = requests.Session()
    sessao.headers.update({"X-API-Key": chave})
    for h in range(n):
        print(f"\n--- hora {h + 1}/{n} ---")
        for bairro, leituras in seq.items():
            r = sessao.post(f"{api}/api/leituras", json=leituras[h], timeout=10)
            if r.status_code != 201:
                print(f"  {bairro:16} ERRO {r.status_code}: {r.text}")
                continue
            dados = r.json()
            respostas.append(dados)
            ag = dados["agente"]
            marca = " <<< ALERTA EMITIDO" if ag["acao"] == "criar" else ""
            if bairro == alvo or ag["acao"] != "nenhuma":
                print(f"  {bairro:16} chuva={leituras[h]['chuva_mm']:5.1f}mm nivel={leituras[h]['nivel_cm']:6.1f}cm "
                      f"p={dados['risco']['probabilidade']:.2f} [{dados['risco']['rotulo']}] agente={ag['acao']}{marca}")
        time.sleep(intervalo)
    return respostas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=os.getenv("API_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--chave", default=os.getenv("DEVICE_API_KEY", "dev-device-key-troque"))
    ap.add_argument("--cenario", choices=["calmo", "tempestade", "replay"], default="tempestade")
    ap.add_argument("--bairro", default="Jardim Helena", choices=list(BAIRROS))
    ap.add_argument("--passos", type=int, default=14)
    ap.add_argument("--intervalo", type=float, default=2.0, help="segundos entre ciclos (1 ciclo = 1 h)")
    ap.add_argument("--semente", type=int, default=7)
    a = ap.parse_args()
    random.seed(a.semente)
    executar(a.api, a.chave, a.cenario, a.bairro, a.passos, a.intervalo)


if __name__ == "__main__":
    main()
