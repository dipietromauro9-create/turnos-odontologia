"""Turno: duración congelada y defensa final de ocupación en PostgreSQL."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
    false,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class EstadoTurno(StrEnum):
    RESERVADO = "reservado"
    CONFIRMADO = "confirmado"
    ATENDIDO = "atendido"
    CANCELADO = "cancelado"
    AUSENTE = "ausente"


EXCLUSION_OCUPACION = "ex_turno_profesional_no_solape"
UNIQUE_CODIGO = "uq_turno_codigo_publico"


class Turno(Base, TenantMixin, AuditMixin):
    __tablename__ = "turno"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="rango_valido"),
        CheckConstraint("length(codigo_publico) = 12", name="codigo_valido"),
        CheckConstraint(
            "(es_sobreturno AND motivo_sobreturno IS NOT NULL "
            "AND length(trim(motivo_sobreturno)) > 0) OR "
            "(NOT es_sobreturno AND motivo_sobreturno IS NULL)",
            name="sobreturno_coherente",
        ),
        UniqueConstraint("codigo_publico", name=UNIQUE_CODIGO),
        Index("ix_turno_tenant_profesional_inicio", "tenant_id", "profesional_id", "inicio"),
        Index("ix_turno_tenant_estado_inicio", "tenant_id", "estado", "inicio"),
        ExcludeConstraint(
            ("tenant_id", "="),
            ("profesional_id", "="),
            (func.tstzrange(column("inicio"), column("fin"), literal_column("'[)'")), "&&"),
            where=text("estado <> 'cancelado'"),
            name=EXCLUSION_OCUPACION,
            using="gist",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profesional.id", ondelete="RESTRICT"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("paciente.id", ondelete="RESTRICT"), nullable=False
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("prestacion.id", ondelete="RESTRICT"), nullable=False
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[EstadoTurno] = mapped_column(
        Enum(EstadoTurno, name="estado_turno", values_callable=lambda cls: [e.value for e in cls]),
        nullable=False,
    )
    codigo_publico: Mapped[str] = mapped_column(String(12), nullable=False)
    es_sobreturno: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    motivo_sobreturno: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo_cancelacion: Mapped[str | None] = mapped_column(Text, nullable=True)
