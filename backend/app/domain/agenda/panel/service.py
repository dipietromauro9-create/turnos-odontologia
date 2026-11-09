"""Construcción del agregado día/semana con alcance RN-AU-03 y tenant resuelto."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from app.core import settings as settings_module
from app.core.errors import DomainError
from app.db.models import Bloqueo, Paciente, Prestacion, Profesional, Turno, Usuario
from app.db.session import TenantSession, require_tenant
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.agenda.panel.schemas import (
    AgendaOut,
    BloqueoAgenda,
    PacienteAgenda,
    PrestacionAgenda,
    ProfesionalAgenda,
    RangoAgenda,
    TurnoAgenda,
)
from app.domain.auth.dependencies import AlcanceAgenda, alcance_agenda
from app.domain.huecos.calculo import a_zona_local


def _zona() -> ZoneInfo:
    return ZoneInfo(settings_module.get_settings().tz)


def rango_del_dia(fecha: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Día calendario completo en la zona del consultorio, semiabierto."""
    inicio = datetime.combine(fecha, time.min, tzinfo=tz)
    return inicio, inicio + timedelta(days=1)


def rango_de_la_semana(desde: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Semana lunes–domingo; un `desde` fuera de lunes se normaliza a su lunes."""
    lunes = desde - timedelta(days=desde.weekday())
    inicio = datetime.combine(lunes, time.min, tzinfo=tz)
    return inicio, inicio + timedelta(days=7)


def agenda_del_dia(
    session: TenantSession,
    usuario: Usuario,
    *,
    fecha: date,
    profesional_id: uuid.UUID | None = None,
) -> AgendaOut:
    tz = _zona()
    inicio, fin = rango_del_dia(fecha, tz)
    return _construir(session, usuario, inicio, fin, profesional_id, tz)


def agenda_de_la_semana(
    session: TenantSession,
    usuario: Usuario,
    *,
    desde: date,
    profesional_id: uuid.UUID | None = None,
) -> AgendaOut:
    tz = _zona()
    inicio, fin = rango_de_la_semana(desde, tz)
    return _construir(session, usuario, inicio, fin, profesional_id, tz)


def _error_no_encontrado() -> DomainError:
    return DomainError(
        "RN-AG-01",
        "El profesional solicitado no existe",
        status_code=404,
        details={"reason": "no_encontrado"},
    )


def _construir(
    session: TenantSession,
    usuario: Usuario,
    inicio: datetime,
    fin: datetime,
    profesional_id: uuid.UUID | None,
    tz: ZoneInfo,
) -> AgendaOut:
    tenant_id = require_tenant().tenant_id
    resuelto = profesional_del_alcance(session, usuario, profesional_id)

    if resuelto is not None and session.get(Profesional, resuelto) is None:
        raise _error_no_encontrado()

    todas = alcance_agenda(usuario) is AlcanceAgenda.TODAS
    profesionales = _profesionales(session, tenant_id, None if todas else resuelto)
    prestaciones = _prestaciones(session, tenant_id)
    turnos = _turnos(session, tenant_id, inicio, fin, resuelto, tz)
    bloqueos = _bloqueos(session, tenant_id, inicio, fin, resuelto, tz)

    return AgendaOut(
        rango=RangoAgenda(desde=a_zona_local(inicio, tz), hasta=a_zona_local(fin, tz)),
        profesionales=profesionales,
        prestaciones=prestaciones,
        turnos=turnos,
        bloqueos=bloqueos,
    )


def _profesionales(
    session: TenantSession, tenant_id: uuid.UUID, resuelto: uuid.UUID | None
) -> list[ProfesionalAgenda]:
    consulta = select(Profesional).where(Profesional.tenant_id == tenant_id)
    if resuelto is not None:
        consulta = consulta.where(Profesional.id == resuelto)
    else:
        consulta = consulta.where(Profesional.activo.is_(True))
    filas = session.execute(consulta.order_by(Profesional.nombre, Profesional.id)).scalars()
    return [
        ProfesionalAgenda(
            id=fila.id,
            nombre=fila.nombre,
            especialidad=fila.especialidad,
            activo=fila.activo,
        )
        for fila in filas
    ]


def _prestaciones(session: TenantSession, tenant_id: uuid.UUID) -> list[PrestacionAgenda]:
    consulta = (
        select(Prestacion)
        .where(Prestacion.tenant_id == tenant_id, Prestacion.activa.is_(True))
        .order_by(Prestacion.nombre, Prestacion.id)
    )
    return [
        PrestacionAgenda(id=fila.id, nombre=fila.nombre, duracion_min=fila.duracion_min)
        for fila in session.execute(consulta).scalars()
    ]


def _turnos(
    session: TenantSession,
    tenant_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
    resuelto: uuid.UUID | None,
    tz: ZoneInfo,
) -> list[TurnoAgenda]:
    consulta = (
        select(Turno, Paciente, Prestacion)
        .join(
            Paciente,
            (Paciente.id == Turno.paciente_id) & (Paciente.tenant_id == tenant_id),
        )
        .join(
            Prestacion,
            (Prestacion.id == Turno.prestacion_id) & (Prestacion.tenant_id == tenant_id),
        )
        .where(
            Turno.tenant_id == tenant_id,
            Turno.inicio >= inicio,
            Turno.inicio < fin,
        )
        .order_by(Turno.inicio, Turno.id)
    )
    if resuelto is not None:
        consulta = consulta.where(Turno.profesional_id == resuelto)

    return [
        TurnoAgenda(
            id=turno.id,
            profesional_id=turno.profesional_id,
            inicio=a_zona_local(turno.inicio, tz),
            fin=a_zona_local(turno.fin, tz),
            estado=turno.estado,
            es_sobreturno=turno.es_sobreturno,
            motivo_sobreturno=turno.motivo_sobreturno,
            motivo_cancelacion=turno.motivo_cancelacion,
            paciente=PacienteAgenda(id=paciente.id, nombre=paciente.nombre),
            prestacion=PrestacionAgenda(
                id=prestacion.id,
                nombre=prestacion.nombre,
                duracion_min=prestacion.duracion_min,
            ),
        )
        for turno, paciente, prestacion in session.execute(consulta)
    ]


def _bloqueos(
    session: TenantSession,
    tenant_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
    resuelto: uuid.UUID | None,
    tz: ZoneInfo,
) -> list[BloqueoAgenda]:
    consulta = select(Bloqueo).where(
        Bloqueo.tenant_id == tenant_id,
        Bloqueo.desde < fin,
        Bloqueo.hasta > inicio,
    )
    if resuelto is not None:
        consulta = consulta.where(
            or_(Bloqueo.profesional_id.is_(None), Bloqueo.profesional_id == resuelto)
        )
    filas = session.execute(consulta.order_by(Bloqueo.desde, Bloqueo.id)).scalars()
    return [
        BloqueoAgenda(
            id=fila.id,
            profesional_id=fila.profesional_id,
            desde=a_zona_local(fila.desde, tz),
            hasta=a_zona_local(fila.hasta, tz),
            motivo=fila.motivo,
        )
        for fila in filas
    ]
