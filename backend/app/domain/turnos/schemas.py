"""Entradas del servicio; los campos calculados nunca provienen del cliente."""

from __future__ import annotations

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.db.models import EstadoTurno


class TurnoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profesional_id: uuid.UUID
    paciente_id: uuid.UUID
    prestacion_id: uuid.UUID
    inicio: AwareDatetime
    es_sobreturno: bool = False
    motivo_sobreturno: str | None = Field(default=None, max_length=2000)


class TurnoPublic(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    profesional_id: uuid.UUID
    paciente_id: uuid.UUID
    prestacion_id: uuid.UUID
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: EstadoTurno
    codigo_publico: str
    es_sobreturno: bool
    motivo_sobreturno: str | None
    motivo_cancelacion: str | None
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime


class TurnoEstado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: EstadoTurno
    motivo_cancelacion: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def motivo_solo_cancelacion(self) -> TurnoEstado:
        if self.motivo_cancelacion is not None and self.estado is not EstadoTurno.CANCELADO:
            raise ValueError("El motivo corresponde solamente a la cancelación")
        return self


class TurnoReprogramar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nuevo_inicio: AwareDatetime


class CancelarTurno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo_cancelacion: str | None = Field(default=None, max_length=2000)


class AccionVacia(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TurnoFiltros(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID | None = None
    estado: EstadoTurno | None = None
    desde: AwareDatetime | None = None
    hasta: AwareDatetime | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def rango_ordenado(self) -> TurnoFiltros:
        if self.desde is not None and self.hasta is not None and self.hasta <= self.desde:
            raise ValueError("hasta debe ser posterior a desde")
        return self
