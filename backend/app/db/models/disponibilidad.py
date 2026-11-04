"""Plantilla semanal: lunes=0, domingo=6; horas locales sin zona horaria."""

import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, Index, Time, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class Disponibilidad(Base, TenantMixin, AuditMixin):
    __tablename__ = "disponibilidad"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="dia_semana_valido"),
        CheckConstraint("hora_hasta > hora_desde", name="rango_valido"),
        UniqueConstraint(
            "tenant_id",
            "profesional_id",
            "dia_semana",
            "hora_desde",
            "hora_hasta",
            name="uq_disponibilidad_tenant_profesional_dia_rango",
        ),
        Index(
            "ix_disponibilidad_tenant_profesional_dia", "tenant_id", "profesional_id", "dia_semana"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profesional.id", ondelete="RESTRICT"), nullable=False
    )
    dia_semana: Mapped[int] = mapped_column(nullable=False)
    hora_desde: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    hora_hasta: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
