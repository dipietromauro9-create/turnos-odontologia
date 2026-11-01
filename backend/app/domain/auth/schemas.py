"""Contratos HTTP de auth (R1: todo schema rechaza campos no declarados)."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import RolUsuario

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class LoginIn(BaseModel):
    """Credenciales del panel. El email se valida pero se compara con CITEXT."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, value: str) -> str:
        limpio = value.strip()
        if not _EMAIL_RE.match(limpio):
            msg = "El email no tiene un formato válido"
            raise ValueError(msg)
        return limpio


class TokenOut(BaseModel):
    """Respuesta del login/refresh: el access viaja en el cuerpo."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class MeOut(BaseModel):
    """Identidad autenticada; nunca incluye credenciales (spec core/auth)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    email: str
    rol: RolUsuario
    es_dueno: bool
