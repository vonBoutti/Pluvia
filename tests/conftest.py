import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# ambiente de teste isolado (banco temporário, credenciais de teste)
_tmp = tempfile.mkdtemp()
os.environ.update({
    "DB_PATH": str(Path(_tmp) / "teste.db"),
    "ADMIN_USER": "admin_teste",
    "ADMIN_PASSWORD": "senha-de-teste-123",
    "DEVICE_API_KEY": "chave-teste-iot",
    "SECRET_KEY": "segredo-de-teste-com-mais-de-32-caracteres",
    "SEED_DEMO": "1",
    "RELATOS_POR_MINUTO": "5",
})

from bigdata.catalogo import GOLD, MODELOS  # noqa: E402

if not (MODELOS / "modelo_risco.joblib").exists() or not (GOLD / "diario_bairro.csv").exists():
    from scripts import preparar  # noqa: E402

    preparar.main()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seguranca import limite_relatos  # noqa: E402


@pytest.fixture()
def cliente():
    limite_relatos.limpar()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def token(cliente):
    r = cliente.post("/api/auth/login", json={"usuario": "admin_teste", "senha": "senha-de-teste-123"})
    return r.json()["access_token"]


@pytest.fixture()
def auth(token):
    return {"Authorization": f"Bearer {token}"}


IOT = {"X-API-Key": "chave-teste-iot"}
