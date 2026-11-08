"""Contratos de exportación (R1: extra='forbid')."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.db.models import EstadoExportacion, TipoExportacion


class ExportacionCreate(BaseModel):
    """Rango opcional; para pacientes se ignora y se exporta todo el tenant."""

    model_config = ConfigDict(extra="forbid")

    desde: AwareDatetime | None = None
    hasta: AwareDatetime | None = None


class ExportacionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tipo: TipoExportacion
    estado: EstadoExportacion
    desde: datetime | None
    hasta: datetime | None
    error: str | None
    creado_en: datetime
    descarga_url: str | None


__all__ = ["ExportacionCreate", "ExportacionPublic"]
