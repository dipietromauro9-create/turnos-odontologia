"""Profesional del consultorio: vínculo opcional 1─1 con un usuario de login."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class Profesional(Base, TenantMixin, AuditMixin):
    __tablename__ = "profesional"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_profesional"),
        UniqueConstraint("usuario_id", name="uq_profesional_usuario_id"),
        Index("ix_profesional_tenant_id_activo", "tenant_id", "activo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuario.id"),
        nullable=True,
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    matricula: Mapped[str | None] = mapped_column(String(50), nullable=True)
    especialidad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )


__all__ = ["Profesional"]
