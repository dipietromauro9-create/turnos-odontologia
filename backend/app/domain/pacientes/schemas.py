"""Contratos HTTP de paciente (R1: `extra='forbid'` en todos los schemas)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.domain.pacientes.telefono import normalizar_telefono

FECHA_NAC_MINIMA = date(1900, 1, 1)
NOMBRE_MAX_LARGO = 200
DOCUMENTO_MAX_LARGO = 50
OBSERVACIONES_MAX_LARGO = 2000


def _nombre_no_vacio(valor: str) -> str:
    limpio = valor.strip()
    if not limpio:
        msg = "El nombre no puede estar vacío"
        raise ValueError(msg)
    return limpio


def _telefono_normalizado(valor: str) -> str:
    return normalizar_telefono(valor)


def _fecha_nac_valida(valor: date | None) -> date | None:
    if valor is None:
        return None
    if valor < FECHA_NAC_MINIMA:
        msg = "La fecha de nacimiento no puede ser anterior a 1900"
        raise ValueError(msg)
    if valor > date.today():
        msg = "La fecha de nacimiento no puede ser futura"
        raise ValueError(msg)
    return valor


class PacienteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=NOMBRE_MAX_LARGO)
    telefono: str
    documento: str | None = Field(default=None, max_length=DOCUMENTO_MAX_LARGO)
    fecha_nac: date | None = None
    observaciones: str | None = Field(default=None, max_length=OBSERVACIONES_MAX_LARGO)

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, valor: str) -> str:
        return _nombre_no_vacio(valor)

    @field_validator("telefono")
    @classmethod
    def _telefono_valido(cls, valor: str) -> str:
        return _telefono_normalizado(valor)

    @field_validator("fecha_nac")
    @classmethod
    def _fecha_valida(cls, valor: date | None) -> date | None:
        return _fecha_nac_valida(valor)


class PacienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=NOMBRE_MAX_LARGO)
    telefono: str | None = None
    documento: str | None = Field(default=None, max_length=DOCUMENTO_MAX_LARGO)
    fecha_nac: date | None = None
    observaciones: str | None = Field(default=None, max_length=OBSERVACIONES_MAX_LARGO)

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, valor: str | None) -> str | None:
        return None if valor is None else _nombre_no_vacio(valor)

    @field_validator("telefono")
    @classmethod
    def _telefono_valido(cls, valor: str | None) -> str | None:
        return None if valor is None else _telefono_normalizado(valor)

    @field_validator("fecha_nac")
    @classmethod
    def _fecha_valida(cls, valor: date | None) -> date | None:
        return _fecha_nac_valida(valor)


class PacienteResumen(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    nombre: str
    telefono: str


class PacienteIdentidadMinima(BaseModel):
    """Contrato de C-09: identidad para reservar, nunca la ficha completa."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    nombre: str
    telefono: str


class PacienteOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    telefono: str
    documento: str | None
    fecha_nac: date | None
    observaciones: str | None
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime


class AdvertenciaDuplicado(BaseModel):
    """RN-PA-01: coincidencias advertidas al alta; `duplicados` se omite sin PII."""

    model_config = ConfigDict(extra="forbid")

    codigo: str
    mensaje: str
    duplicados: list[PacienteResumen] | None = None


class PacienteCreadoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente: PacienteOut
    advertencia: AdvertenciaDuplicado | None = None


__all__ = [
    "AdvertenciaDuplicado",
    "PacienteCreate",
    "PacienteCreadoOut",
    "PacienteIdentidadMinima",
    "PacienteOut",
    "PacienteResumen",
    "PacienteUpdate",
]
