"""Contratos del motor de huecos: consulta validada y salida sin datos de pacientes."""

from __future__ import annotations

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.domain.huecos.calculo import RANGO_MAXIMO, RANGO_MAXIMO_DIAS


class HuecosQuery(BaseModel):
    """Parámetros obligatorios de `GET /disponibilidad/huecos` (R1: sin extras)."""

    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID
    desde: AwareDatetime
    hasta: AwareDatetime

    @model_validator(mode="after")
    def validar_rango(self) -> HuecosQuery:
        if self.hasta <= self.desde:
            msg = "El fin del rango debe ser posterior al inicio"
            raise ValueError(msg)
        if self.hasta - self.desde > RANGO_MAXIMO:
            msg = f"El rango máximo es de {RANGO_MAXIMO_DIAS} días; paginá en tramos menores"
            raise ValueError(msg)
        return self


class HuecoPublic(BaseModel):
    """Intervalo reservable expuesto por la API; NUNCA incluye datos de pacientes."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    inicio: AwareDatetime
    fin: AwareDatetime
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID
