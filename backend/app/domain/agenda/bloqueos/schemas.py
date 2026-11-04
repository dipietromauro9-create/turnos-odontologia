"""Instantes absolutos conscientes de zona y motivo obligatorio del cierre."""

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class BloqueoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID | None = None
    desde: AwareDatetime
    hasta: AwareDatetime
    motivo: str = Field(min_length=1)

    @field_validator("motivo")
    @classmethod
    def motivo_no_vacio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El cierre requiere un motivo")
        return value


class BloqueoPublic(BloqueoCreate):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime
