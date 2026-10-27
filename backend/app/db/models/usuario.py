"""Usuario del consultorio: rol, dueño y email único case-insensitive por tenant."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    false,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin, TenantMixin


class RolUsuario(StrEnum):
    RECEPCION = "recepcion"
    PROFESIONAL = "profesional"


class Usuario(Base, TenantMixin, AuditMixin):
    __tablename__ = "usuario"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_usuario"),
        UniqueConstraint("tenant_id", "email", name="uq_usuario_tenant_id_email"),
        CheckConstraint("NOT es_dueno OR rol = 'profesional'", name="dueno_profesional"),
        Index("ix_usuario_tenant_id_rol", "tenant_id", "rol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        Enum(
            RolUsuario,
            native_enum=False,
            create_constraint=True,
            length=20,
            name="rol",
            values_callable=lambda enum_cls: [miembro.value for miembro in enum_cls],
        ),
        nullable=False,
    )
    es_dueno: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
