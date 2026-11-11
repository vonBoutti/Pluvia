"""Práticas de segurança do Pluvia.

1. Autenticação JWT (HS256, expiração) para o painel da Defesa Civil.
2. Senha do administrador guardada só como hash PBKDF2-SHA256 + salt; comparação em tempo constante.
3. Chave de API (X-API-Key) para as estações IoT enviarem leituras.
4. Validação de entrada com Pydantic (tipos, faixas, tamanhos) — ver schemas.py.
5. Proteção de dados (LGPD): telefone do cidadão nunca é salvo em claro (hash + máscara);
   relatos não guardam IP nem nome.
6. Limite de requisições (rate limit) no envio de relatos, contra spam/robôs.
7. Cabeçalhos HTTP de segurança (CSP, X-Frame-Options, nosniff) — ver main.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config

_ITERACOES = 200_000


def hash_senha(senha: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, _ITERACOES)
    return f"{salt.hex()}${dk.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    salt_hex, dk_hex = armazenado.split("$")
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt_hex), _ITERACOES)
    return hmac.compare_digest(dk.hex(), dk_hex)


# hash calculado uma vez na inicialização; a senha em claro não fica em estrutura nenhuma do app
_ADMIN_HASH = hash_senha(config.ADMIN_PASSWORD) if config.ADMIN_PASSWORD else None


def autenticar(usuario: str, senha: str) -> bool:
    if not _ADMIN_HASH:
        return False  # sem senha configurada, ninguém entra
    usuario_ok = hmac.compare_digest(usuario, config.ADMIN_USER)
    return verificar_senha(senha, _ADMIN_HASH) and usuario_ok


def criar_token(usuario: str) -> str:
    agora = datetime.now(timezone.utc)
    payload = {"sub": usuario, "iat": agora, "exp": agora + timedelta(minutes=config.TOKEN_MINUTOS), "papel": "defesa_civil"}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


_bearer = HTTPBearer(auto_error=False)


def exigir_token(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token ausente", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(cred.credentials, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado") from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from err
    return payload["sub"]


def exigir_chave_dispositivo(x_api_key: str | None = Header(default=None)) -> None:
    if not config.DEVICE_API_KEY or not x_api_key or not hmac.compare_digest(x_api_key, config.DEVICE_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chave do dispositivo inválida")


# ---- LGPD -----------------------------------------------------------------
def so_digitos(tel: str) -> str:
    return re.sub(r"\D", "", tel)


def hash_contato(tel: str) -> str:
    """HMAC com 'pepper' próprio (estável entre reinícios) — permite deduplicar sem guardar o número."""
    return hmac.new(config.CONTATO_PEPPER.encode(), so_digitos(tel).encode(), hashlib.sha256).hexdigest()


def mascarar_telefone(tel: str) -> str:
    d = so_digitos(tel)
    return f"({d[:2]}) *****-{d[-4:]}" if len(d) >= 10 else "****"


# ---- Rate limit (janela deslizante em memória) ------------------------------
class LimiteRequisicoes:
    def __init__(self, maximo: int, janela_s: int = 60):
        self.maximo, self.janela = maximo, janela_s
        self._hist: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        chave = request.client.host if request.client else "anon"
        agora = time.monotonic()
        fila = self._hist[chave]
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        if len(fila) >= self.maximo:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitos envios. Aguarde um minuto.")
        fila.append(agora)

    def limpar(self) -> None:
        self._hist.clear()


limite_relatos = LimiteRequisicoes(config.RELATOS_POR_MINUTO)
