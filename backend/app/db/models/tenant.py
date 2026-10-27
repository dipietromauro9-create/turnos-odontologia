"""Tenant raíz: el consultorio. `slug` único e inmutable tras la creación."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import AuditMixin


class SlugInmutableError(ValueError):
    """El slug identifica al consultorio y no puede reescribirse."""


class Tenant(Base, AuditMixin):
    __tablename__ = "tenant"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_tenant"),
        UniqueConstraint("slug", name="uq_tenant_slug"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_no_vacio"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)


@event.listens_for(Tenant, "before_update")
def _slug_inmutable(_mapper: object, _connection: object, target: Tenant) -> None:
    historial = inspect(target).attrs.slug.history
    if historial.has_changes():
        raise SlugInmutableError("El slug de un tenant no puede modificarse")
