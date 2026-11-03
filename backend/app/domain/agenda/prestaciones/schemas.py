"""Contratos HTTP del catálogo de prestaciones (R1: `extra='forbid'`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalizar_nombre(value: str) -> str:
    limpio = value.strip()
    if not limpio:
        msg = "El nombre no puede estar vacío"
        raise ValueError(msg)
    return limpio


class PrestacionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=200)
    duracion_min: int
    precio_ref: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, value: str) -> str:
        return _normalizar_nombre(value)


class PrestacionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    duracion_min: int | None = None
    precio_ref: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    activa: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalizar_nombre(value)


class PrestacionOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    duracion_min: int
    precio_ref: Decimal | None
    activa: bool
    creado_en: datetime
    actualizado_en: datetime


__all__ = ["PrestacionCreate", "PrestacionOut", "PrestacionUpdate"]
