"""Modelos ORM transversales; importarlos completa `Base.metadata` para Alembic."""

from app.db.models.bloqueo import Bloqueo
from app.db.models.disponibilidad import Disponibilidad
from app.db.models.mixins import AuditMixin, TenantMixin
from app.db.models.paciente import Paciente
from app.db.models.prestacion import Prestacion
from app.db.models.profesional import Profesional
from app.db.models.tenant import SlugInmutableError, Tenant
from app.db.models.turno import EstadoTurno, Turno
from app.db.models.usuario import RolUsuario, Usuario

__all__ = [
    "AuditMixin",
    "Bloqueo",
    "Disponibilidad",
    "EstadoTurno",
    "Paciente",
    "Prestacion",
    "Profesional",
    "RolUsuario",
    "SlugInmutableError",
    "Tenant",
    "TenantMixin",
    "Turno",
    "Usuario",
]
