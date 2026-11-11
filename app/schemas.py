"""Contratos da API com validação de entrada (segurança: nada chega ao banco sem passar aqui)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from bigdata.catalogo import BAIRROS, ESTACAO_PARA_BAIRRO


class Login(BaseModel):
    usuario: str = Field(min_length=3, max_length=40)
    senha: str = Field(min_length=6, max_length=128)


class Leitura(BaseModel):
    estacao: str = Field(examples=["AC-01"])
    chuva_mm: float = Field(ge=0, le=200, description="pluviômetro, mm na última hora")
    nivel_cm: float = Field(ge=0, le=600, description="ultrassônico, nível do córrego")
    temp_c: float | None = Field(default=None, ge=-10, le=50)
    ts: datetime | None = None

    @field_validator("estacao")
    @classmethod
    def estacao_conhecida(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ESTACAO_PARA_BAIRRO:
            raise ValueError("estação não cadastrada")
        return v


class _ComBairro(BaseModel):
    bairro: str

    @field_validator("bairro")
    @classmethod
    def bairro_valido(cls, v: str) -> str:
        if v not in BAIRROS:
            raise ValueError("bairro não atendido")
        return v


class NovoRelato(_ComBairro):
    texto: str = Field(min_length=10, max_length=500)

    @field_validator("texto")
    @classmethod
    def limpar(cls, v: str) -> str:
        v = " ".join(v.split())
        if "<" in v or ">" in v:
            raise ValueError("texto contém caracteres não permitidos")
        return v


class NovaInscricao(_ComBairro):
    telefone: str = Field(min_length=10, max_length=20, pattern=r"^[\d\s()+-]+$")
    aceite_lgpd: bool

    @field_validator("aceite_lgpd")
    @classmethod
    def precisa_aceite(cls, v: bool) -> bool:
        if not v:
            raise ValueError("é preciso aceitar o uso do telefone apenas para alertas")
        return v


class AtualizarRelato(BaseModel):
    status: Literal["aberto", "em_atendimento", "resolvido"]
