"""Prestación del catálogo: duración válida congelada por turno y precio informativo."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class Prestacion(Base, TenantMixin, AuditMixin):
    __tablename__ = "prestacion"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_prestacion"),
        CheckConstraint("duracion_min > 0 AND duracion_min % 5 = 0", name="duracion_multiplo_5"),
        CheckConstraint("precio_ref IS NULL OR precio_ref >= 0", name="precio_no_negativo"),
        Index("ix_prestacion_tenant_id_activa", "tenant_id", "activa"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_ref: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )


__all__ = ["Prestacion"]
