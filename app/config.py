"""Configuração lida de variáveis de ambiente (nunca segredos fixos no código de produção)."""
import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("DB_PATH", RAIZ / "app" / "pluvia.db"))
# Se SECRET_KEY não for definida, gera uma aleatória a cada inicialização (tokens expiram no restart).
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
ADMIN_USER = os.getenv("ADMIN_USER", "defesacivil")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")  # obrigatório definir; ver .env.example
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "")  # chave das estações IoT
CONTATO_PEPPER = os.getenv("CONTATO_PEPPER", "troque-este-pepper-em-producao")
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "60"))
RELATOS_POR_MINUTO = int(os.getenv("RELATOS_POR_MINUTO", "5"))
SEED_DEMO = os.getenv("SEED_DEMO", "1") == "1"
