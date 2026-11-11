"""Persistência em SQLite (arquivo único, sem servidor — roda em qualquer máquina)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estacao TEXT NOT NULL, bairro TEXT NOT NULL, ts TEXT NOT NULL,
    chuva_mm REAL NOT NULL, nivel_cm REAL NOT NULL, temp_c REAL,
    probabilidade REAL, nivel_risco TEXT
);
CREATE INDEX IF NOT EXISTS ix_leituras_estacao ON leituras(estacao, id);
CREATE INDEX IF NOT EXISTS ix_leituras_bairro ON leituras(bairro, id);

CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bairro TEXT NOT NULL, nivel TEXT NOT NULL, mensagem TEXT NOT NULL,
    acao_defesa_civil TEXT, motivo TEXT, probabilidade REAL,
    criado_em TEXT NOT NULL, encerrado_em TEXT, ativo INTEGER NOT NULL DEFAULT 1,
    destinatarios INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_alertas_bairro ON alertas(bairro, ativo, id);

CREATE TABLE IF NOT EXISTS relatos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bairro TEXT NOT NULL, texto TEXT NOT NULL,
    categoria TEXT, severidade TEXT, confianca REAL, orgao TEXT, prazo TEXT,
    revisao_humana INTEGER, regra_urgencia INTEGER,
    status TEXT NOT NULL DEFAULT 'aberto', criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inscricoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bairro TEXT NOT NULL, contato_hash TEXT NOT NULL, contato_mascarado TEXT NOT NULL,
    criado_em TEXT NOT NULL, UNIQUE(bairro, contato_hash)
);
"""


def conectar() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def inicializar() -> None:
    with conectar() as con:
        con.executescript(SCHEMA)


@contextmanager
def transacao():
    con = conectar()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def linhas(rows) -> list[dict]:
    return [dict(r) for r in rows]
