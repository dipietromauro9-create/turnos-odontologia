"""Modelos ORM transversales; importarlos completa `Base.metadata` para Alembic."""

from app.db.models.mixins import AuditMixin, TenantMixin
from app.db.models.tenant import SlugInmutableError, Tenant
from app.db.models.usuario import RolUsuario, Usuario

__all__ = [
    "AuditMixin",
    "RolUsuario",
    "SlugInmutableError",
    "Tenant",
    "TenantMixin",
    "Usuario",
]
