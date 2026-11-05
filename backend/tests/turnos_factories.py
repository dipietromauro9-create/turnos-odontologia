"""Catálogo y plantilla ficticios para probar el servicio único de turnos."""

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import (
    Disponibilidad,
    Paciente,
    Prestacion,
    Profesional,
    RolUsuario,
    Tenant,
    Usuario,
)
from tests.factories import crear_prestacion, crear_profesional, crear_tenant, crear_usuario

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2030, 6, 1, 8, tzinfo=TZ)
INICIO = datetime(2030, 6, 3, 9, tzinfo=TZ)  # lunes


@dataclass(frozen=True)
class EntornoTurnos:
    tenant: Tenant
    usuario: Usuario
    profesional: Profesional
    prestacion: Prestacion
    paciente: Paciente

    def datos(self, **cambios: object) -> dict[str, object]:
        valores = dict(
            profesional_id=self.profesional.id,
            prestacion_id=self.prestacion.id,
            paciente_id=self.paciente.id,
            inicio=INICIO,
        )
        valores.update(cambios)
        return valores


def entorno_turnos(session: Session, slug: str = "demo") -> EntornoTurnos:
    tenant = crear_tenant(session, slug)
    usuario = crear_usuario(session, tenant, f"dueno@{slug}", RolUsuario.PROFESIONAL, es_dueno=True)
    profesional = crear_profesional(session, tenant, usuario=usuario)
    prestacion = crear_prestacion(session, tenant)
    paciente = Paciente(
        tenant_id=tenant.id,
        creado_por_usuario_id=usuario.id,
        nombre="Paciente Ficticio",
        telefono="1145550001",
    )
    session.add(paciente)
    session.add(
        Disponibilidad(
            tenant_id=tenant.id,
            profesional_id=profesional.id,
            dia_semana=0,
            hora_desde=time(9),
            hora_hasta=time(13),
        )
    )
    session.commit()
    return EntornoTurnos(tenant, usuario, profesional, prestacion, paciente)
