"""Recordatorio manual de turno: un aviso por turno, auditable y tenant-scoped.

RN-CO-01: existe exactamente un recordatorio por turno confirmado próximo; la
unicidad la defiende la base (`uq_recordatorio_turno`). RN-CO-03: marcar
`enviado` exige registrar quién lo envió.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin

TABLA = "recordatorio"
PK_RECORDATORIO = "pk_recordatorio"
UNIQUE_TURNO = "uq_recordatorio_turno"
CHECK_ENVIADO_POR = "enviado_por_coherente"
IX_TENANT_ESTADO = "ix_recordatorio_tenant_estado"


class CanalRecordatorio(StrEnum):
    WHATSAPP_MANUAL = "whatsapp_manual"


class EstadoRecordatorio(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"


class Recordatorio(Base, TenantMixin, AuditMixin):
    __tablename__ = TABLA
    __table_args__ = (
        PrimaryKeyConstraint("id", name=PK_RECORDATORIO),
        UniqueConstraint("tenant_id", "turno_id", name=UNIQUE_TURNO),
        CheckConstraint(
            "estado <> 'enviado' OR enviado_por IS NOT NULL",
            name=CHECK_ENVIADO_POR,
        ),
        Index(IX_TENANT_ESTADO, "tenant_id", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("turno.id", ondelete="CASCADE"),
        nullable=False,
    )
    canal: Mapped[CanalRecordatorio] = mapped_column(
        Enum(
            CanalRecordatorio,
            name="canal_recordatorio",
            values_callable=lambda cls: [e.value for e in cls],
        ),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[EstadoRecordatorio] = mapped_column(
        Enum(
            EstadoRecordatorio,
            name="estado_recordatorio",
            values_callable=lambda cls: [e.value for e in cls],
        ),
        nullable=False,
    )
    enviado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )


__all__ = ["CanalRecordatorio", "EstadoRecordatorio", "Recordatorio"]
