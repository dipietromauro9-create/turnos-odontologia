"""Contrato del agregador de agenda: payload mínimo, sin ficha clínica."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.db.models import EstadoTurno


class RangoAgenda(BaseModel):
    """Rango semiabierto resuelto en la zona horaria del consultorio."""

    model_config = ConfigDict(extra="forbid")

    desde: AwareDatetime
    hasta: AwareDatetime


class ProfesionalAgenda(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    especialidad: str | None
    activo: bool


class PrestacionAgenda(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    duracion_min: int


class PacienteAgenda(BaseModel):
    """Solo lo mínimo para identificar la tarjeta; nunca documento ni teléfono."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str


class TurnoAgenda(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    profesional_id: uuid.UUID
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: EstadoTurno
    es_sobreturno: bool
    motivo_sobreturno: str | None
    motivo_cancelacion: str | None
    paciente: PacienteAgenda
    prestacion: PrestacionAgenda


class BloqueoAgenda(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    profesional_id: uuid.UUID | None
    desde: AwareDatetime
    hasta: AwareDatetime
    motivo: str


class AgendaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rango: RangoAgenda
    profesionales: list[ProfesionalAgenda]
    prestaciones: list[PrestacionAgenda]
    turnos: list[TurnoAgenda]
    bloqueos: list[BloqueoAgenda]


class DiaQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: date
    profesional_id: uuid.UUID | None = None


class SemanaQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desde: date
    profesional_id: uuid.UUID | None = None


__all__ = [
    "AgendaOut",
    "BloqueoAgenda",
    "DiaQuery",
    "PacienteAgenda",
    "PrestacionAgenda",
    "ProfesionalAgenda",
    "RangoAgenda",
    "SemanaQuery",
    "TurnoAgenda",
]
