"""Contratos de reportes (R1: extra='forbid')."""

from __future__ import annotations

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class ReporteFiltros(BaseModel):
    """Rango obligatorio y filtro opcional por profesional."""

    model_config = ConfigDict(extra="forbid")

    desde: AwareDatetime
    hasta: AwareDatetime
    profesional_id: uuid.UUID | None = None


class OcupacionProfesional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    nombre: str
    turnos_activos: int
    minutos_disponibles: int
    minutos_ocupados: int
    ocupacion: float


class AusenciasProfesional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    nombre: str
    atendidos: int
    ausentes: int
    tasa_ausencia: float


class RecordatoriosProfesional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    nombre: str
    turnos_confirmados: int
    recordatorios_enviados: int
    ratio: float


__all__ = [
    "AusenciasProfesional",
    "OcupacionProfesional",
    "RecordatoriosProfesional",
    "ReporteFiltros",
]
