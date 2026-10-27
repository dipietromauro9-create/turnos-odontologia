"""Mixins reutilizables: frontera de tenant y auditoría con timestamptz."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class TenantMixin:
    """Todo modelo de dominio cuelga de un tenant (R3: nada sin frontera)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tenant.id"),
        nullable=False,
    )


class AuditMixin:
    """Timestamps siempre con zona horaria (RN-GL-03)."""

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
