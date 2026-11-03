"""Contratos HTTP del directorio de profesionales (R1: `extra='forbid'`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalizar_nombre(value: str) -> str:
    limpio = value.strip()
    if not limpio:
        msg = "El nombre no puede estar vacío"
        raise ValueError(msg)
    return limpio


class ProfesionalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=200)
    usuario_id: uuid.UUID | None = None
    matricula: str | None = Field(default=None, max_length=50)
    especialidad: str | None = Field(default=None, max_length=120)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, value: str) -> str:
        return _normalizar_nombre(value)


class ProfesionalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    usuario_id: uuid.UUID | None = None
    matricula: str | None = Field(default=None, max_length=50)
    especialidad: str | None = Field(default=None, max_length=120)
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalizar_nombre(value)


class ProfesionalOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    usuario_id: uuid.UUID | None
    nombre: str
    matricula: str | None
    especialidad: str | None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime


__all__ = ["ProfesionalCreate", "ProfesionalOut", "ProfesionalUpdate"]
