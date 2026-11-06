"""Schemas Pydantic para el turnero público (R1: extra='forbid')."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.db.models import EstadoTurno
from app.domain.pacientes.telefono import normalizar_telefono

NOMBRE_MAX_LARGO = 200
MOTIVO_MAX_LARGO = 2000
CODIGO_MAX_LARGO = 64


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ConsultorioPublico(BaseSchema):
    nombre: str
    slug: str


class ProfesionalPublico(BaseSchema):
    id: uuid.UUID
    nombre: str
    especialidad: str | None = None


class PrestacionPublica(BaseSchema):
    id: uuid.UUID
    nombre: str
    duracion_min: int
    precio_ref: Decimal | None = None


class CatalogoPublicoResponse(BaseSchema):
    consultorio: ConsultorioPublico
    profesionales: list[ProfesionalPublico]
    prestaciones: list[PrestacionPublica]


class HuecoPublicoResponse(BaseSchema):
    inicio: AwareDatetime
    fin: AwareDatetime
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID


class ReservaPublicaCreate(BaseSchema):
    """Datos mínimos de la reserva anónima; `fin` y `estado` los calcula el backend."""

    nombre: str = Field(min_length=1, max_length=NOMBRE_MAX_LARGO)
    telefono: str
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID
    inicio: AwareDatetime

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            msg = "El nombre no puede estar vacío"
            raise ValueError(msg)
        return limpio

    @field_validator("telefono")
    @classmethod
    def _telefono_valido(cls, valor: str) -> str:
        return normalizar_telefono(valor)


class ReservaPublicaOut(BaseSchema):
    """Respuesta de reserva: código de gestión y horario; nunca datos del paciente."""

    codigo_publico: str
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: EstadoTurno
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID
    duplicado_advertencia: bool


class TurnoPublicoOut(BaseSchema):
    """Detalle de un turno propio por código público, sin PII de terceros."""

    codigo_publico: str
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: EstadoTurno
    profesional: ProfesionalPublico
    prestacion: PrestacionPublica


class CancelarPublicoIn(BaseSchema):
    codigo: str = Field(min_length=1, max_length=CODIGO_MAX_LARGO)
    motivo_cancelacion: str | None = Field(default=None, max_length=MOTIVO_MAX_LARGO)


class ReprogramarPublicoIn(BaseSchema):
    codigo: str = Field(min_length=1, max_length=CODIGO_MAX_LARGO)
    nuevo_inicio: AwareDatetime


__all__ = [
    "CancelarPublicoIn",
    "CatalogoPublicoResponse",
    "ConsultorioPublico",
    "HuecoPublicoResponse",
    "PrestacionPublica",
    "ProfesionalPublico",
    "ReprogramarPublicoIn",
    "ReservaPublicaCreate",
    "ReservaPublicaOut",
    "TurnoPublicoOut",
]
