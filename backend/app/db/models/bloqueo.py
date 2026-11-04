"""Cierre puntual; profesional nulo significa todo el consultorio (RN-AG-02)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class Bloqueo(Base, TenantMixin, AuditMixin):
    __tablename__ = "bloqueo"
    __table_args__ = (
        CheckConstraint("hasta > desde", name="rango_valido"),
        CheckConstraint("length(trim(motivo)) > 0", name="motivo_no_vacio"),
        Index("ix_bloqueo_tenant_profesional_desde", "tenant_id", "profesional_id", "desde"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    profesional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profesional.id", ondelete="RESTRICT"), nullable=True
    )
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
