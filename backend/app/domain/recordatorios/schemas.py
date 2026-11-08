"""Contratos de la cola de recordatorios (R1: extra='forbid')."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import CanalRecordatorio, EstadoRecordatorio


class RecordatorioPublic(BaseModel):
    """Recordatorio con los datos del turno que necesita recepción para enviarlo."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    turno_id: uuid.UUID
    canal: CanalRecordatorio
    estado: EstadoRecordatorio
    texto: str
    inicio: datetime
    paciente: str
    profesional: str
    enviado_por: uuid.UUID | None
    creado_en: datetime


__all__ = ["RecordatorioPublic"]
