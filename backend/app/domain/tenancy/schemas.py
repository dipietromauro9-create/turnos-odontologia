"""Contratos de borde del dominio de tenancy (Pydantic v2, R1)."""

from __future__ import annotations

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.db.models.usuario import RolUsuario


class TenantOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    slug: str
    nombre: str
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime


class UsuarioOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    nombre: str
    email: str
    rol: RolUsuario
    es_dueno: bool
    activo: bool
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime
