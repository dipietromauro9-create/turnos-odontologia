"""Horas de pared del consultorio; no son instantes con zona horaria."""

import uuid
from datetime import time

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class DisponibilidadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    dia_semana: int = Field(ge=0, le=6)
    hora_desde: time
    hora_hasta: time

    @field_validator("hora_desde", "hora_hasta")
    @classmethod
    def sin_zona(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("La plantilla usa horas locales sin zona horaria")
        return value


class DisponibilidadPublic(DisponibilidadCreate):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime
