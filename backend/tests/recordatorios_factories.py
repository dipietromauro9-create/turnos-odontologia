"""Escenarios ficticios de turnos confirmados para los tests de recordatorios (R9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import EstadoTurno, Paciente, Prestacion, Profesional, Tenant, Turno
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

AHORA = datetime(2030, 6, 3, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Escenario:
    tenant: Tenant
    profesional: Profesional
    prestacion: Prestacion
    paciente: Paciente
    turno: Turno


def crear_escenario(
    session: Session,
    *,
    slug: str = "demo",
    codigo: str = "abcdefgh1234",
    offset_hs: float = 36,
    estado: EstadoTurno = EstadoTurno.CONFIRMADO,
    creado_en: datetime | None = None,
    paciente_nombre: str = "Paciente Ficticio",
    profesional_nombre: str = "Dra. Ficticia",
    telefono: str = "1145550001",
) -> Escenario:
    """Tenant + profesional + prestación + paciente + turno con inicio relativo a AHORA."""
    tenant = crear_tenant(session, slug)
    profesional = crear_profesional(session, tenant, nombre=profesional_nombre)
    prestacion = crear_prestacion(session, tenant)
    paciente = Paciente(tenant_id=tenant.id, nombre=paciente_nombre, telefono=telefono)
    session.add(paciente)
    session.commit()
    inicio = AHORA + timedelta(hours=offset_hs)
    turno = Turno(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado,
        codigo_publico=codigo,
        es_sobreturno=False,
    )
    if creado_en is not None:
        turno.creado_en = creado_en
    session.add(turno)
    session.commit()
    return Escenario(tenant, profesional, prestacion, paciente, turno)
