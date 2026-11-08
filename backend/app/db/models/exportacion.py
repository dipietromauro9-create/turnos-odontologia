"""Exportación CSV asíncrona: estado, contenido y trazabilidad por tenant.

El worker deja el CSV en `contenido` (Text) para que `api` y `worker` no
necesiten un volumen compartido; ver design.md — Decisión 4.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin

TABLA = "exportacion"
PK_EXPORTACION = "pk_exportacion"
IX_TENANT_ESTADO = "ix_exportacion_tenant_estado"
IX_TENANT_CREADO = "ix_exportacion_tenant_creado_en"


class TipoExportacion(StrEnum):
    TURNOS = "turnos"
    PACIENTES = "pacientes"


class EstadoExportacion(StrEnum):
    PENDIENTE = "pendiente"
    PROCESANDO = "procesando"
    LISTO = "listo"
    FALLIDO = "fallido"


class Exportacion(Base, TenantMixin, AuditMixin):
    __tablename__ = TABLA
    __table_args__ = (
        PrimaryKeyConstraint("id", name=PK_EXPORTACION),
        Index(IX_TENANT_ESTADO, "tenant_id", "estado"),
        Index(IX_TENANT_CREADO, "tenant_id", "creado_en"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tipo: Mapped[TipoExportacion] = mapped_column(
        Enum(
            TipoExportacion,
            name="tipo_exportacion",
            values_callable=lambda cls: [e.value for e in cls],
        ),
        nullable=False,
    )
    estado: Mapped[EstadoExportacion] = mapped_column(
        Enum(
            EstadoExportacion,
            name="estado_exportacion",
            values_callable=lambda cls: [e.value for e in cls],
        ),
        nullable=False,
        default=EstadoExportacion.PENDIENTE,
        server_default=text("'pendiente'"),
    )
    desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contenido: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )


__all__ = ["EstadoExportacion", "Exportacion", "TipoExportacion"]
