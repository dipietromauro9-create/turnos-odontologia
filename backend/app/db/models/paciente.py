"""Paciente del consultorio: ficha básica tenant-scoped y búsqueda por nombre/teléfono.

Nota de deuda (RN-PA-03 / DD-07 / IN-01): el borrado es físico y no existe audit
trail ni soft delete en v1; revertirlo es prioridad post-MVP.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin

TABLA = "paciente"
PK_PACIENTE = "pk_paciente"
CHECK_NOMBRE_NO_VACIO = "nombre_no_vacio"
CHECK_TELEFONO_DIGITOS = "telefono_digitos"
IX_TENANT_TELEFONO = "ix_paciente_tenant_id_telefono"
IX_TENANT_CREADO_POR = "ix_paciente_tenant_id_creado_por_usuario_id"
IX_TENANT_NOMBRE_TRGM = "ix_paciente_tenant_id_nombre_trgm"

TELEFONO_MIN_DIGITOS = 6
TELEFONO_MAX_DIGITOS = 15
NOMBRE_MAX_LARGO = 200
DOCUMENTO_MAX_LARGO = 50
OBSERVACIONES_MAX_LARGO = 2000

_check_telefono = f"telefono ~ '^[0-9]{{{TELEFONO_MIN_DIGITOS},{TELEFONO_MAX_DIGITOS}}}$'"


class Paciente(Base, TenantMixin, AuditMixin):
    __tablename__ = TABLA
    __table_args__ = (
        PrimaryKeyConstraint("id", name=PK_PACIENTE),
        CheckConstraint("length(trim(nombre)) > 0", name=CHECK_NOMBRE_NO_VACIO),
        CheckConstraint(_check_telefono, name=CHECK_TELEFONO_DIGITOS),
        Index(IX_TENANT_TELEFONO, "tenant_id", "telefono"),
        Index(
            IX_TENANT_CREADO_POR,
            "tenant_id",
            "creado_por_usuario_id",
        ),
        Index(
            IX_TENANT_NOMBRE_TRGM,
            "tenant_id",
            text("lower(nombre) gin_trgm_ops"),
            postgresql_using="gin",
            postgresql_ops={"tenant_id": "uuid_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    creado_por_usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )
    nombre: Mapped[str] = mapped_column(String(NOMBRE_MAX_LARGO), nullable=False)
    telefono: Mapped[str] = mapped_column(String(TELEFONO_MAX_DIGITOS), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(DOCUMENTO_MAX_LARGO), nullable=True)
    fecha_nac: Mapped[date | None] = mapped_column(Date, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(
        String(OBSERVACIONES_MAX_LARGO), nullable=True
    )


__all__ = ["Paciente"]
