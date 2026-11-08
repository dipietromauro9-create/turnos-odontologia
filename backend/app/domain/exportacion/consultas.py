"""Consultas de lectura para el CSV; separadas para no mezclar escrituras (R4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import Paciente, Prestacion, Profesional, Turno
from app.db.session import TenantSession


def turnos(
    session: TenantSession, desde: datetime | None, hasta: datetime | None
) -> list[tuple[object, str, str, str, str]]:
    consulta = (
        select(
            Turno,
            Profesional.nombre,
            Prestacion.nombre,
            Paciente.nombre,
            Paciente.telefono,
        )
        .join(Profesional, Profesional.id == Turno.profesional_id)
        .join(Prestacion, Prestacion.id == Turno.prestacion_id)
        .join(Paciente, Paciente.id == Turno.paciente_id)
        .order_by(Turno.inicio, Turno.id)
    )
    if desde is not None:
        consulta = consulta.where(Turno.inicio >= desde)
    if hasta is not None:
        consulta = consulta.where(Turno.inicio < hasta)
    return [tuple(fila) for fila in session.execute(consulta).all()]  # type: ignore[misc]


def pacientes(session: TenantSession) -> list[Paciente]:
    return list(
        session.execute(select(Paciente).order_by(Paciente.nombre, Paciente.id)).scalars()
    )
