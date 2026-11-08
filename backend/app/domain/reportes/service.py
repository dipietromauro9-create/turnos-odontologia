"""Servicio de reportes: rango, alcance por rol y cálculo puro (RN-RP-01)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.errors import DomainError
from app.core.settings import get_settings
from app.db.models import Bloqueo, Disponibilidad, EstadoTurno, Profesional, Turno, Usuario
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.persistence import UnitOfWork
from app.domain.reportes.calculo import (
    Franja,
    Intervalo,
    TurnoMetrica,
    resumen_ausencias,
    resumen_ocupacion,
    resumen_recordatorios,
)
from app.domain.reportes.repository import ReportesRepository
from app.domain.reportes.schemas import (
    AusenciasProfesional,
    OcupacionProfesional,
    RecordatoriosProfesional,
    ReporteFiltros,
)

MAX_DIAS = 366


def _error(reason: str, mensaje: str, status: int) -> DomainError:
    return DomainError("RN-RP-01", mensaje, status_code=status, details={"reason": reason})


def _validar_rango(desde: datetime, hasta: datetime) -> None:
    if hasta <= desde or hasta - desde > timedelta(days=MAX_DIAS):
        raise _error(
            "rango_invalido",
            "El rango del reporte no es válido o supera el máximo permitido",
            422,
        )


def _contexto(
    usuario: Usuario,
    desde: datetime,
    hasta: datetime,
    profesional_id: uuid.UUID | None,
) -> tuple[
    list[Profesional],
    list[Disponibilidad],
    list[Bloqueo],
    list[Turno],
    dict[uuid.UUID, int],
]:
    _validar_rango(desde, hasta)
    with UnitOfWork() as uow:
        alcance = profesional_del_alcance(uow.session, usuario, profesional_id)
        repositorio = ReportesRepository(uow.session)
        profesionales = repositorio.profesionales(alcance)
        if profesional_id is not None and not profesionales:
            raise _error("no_encontrado", "El profesional no existe", 404)
        ids = [profesional.id for profesional in profesionales]
        return (
            profesionales,
            repositorio.franjas(ids),
            repositorio.bloqueos(ids, desde, hasta),
            repositorio.turnos(ids, desde, hasta),
            repositorio.recordatorios_enviados(ids, desde, hasta),
        )


def _franjas(filas: list[Disponibilidad]) -> dict[uuid.UUID, list[Franja]]:
    agrupadas: dict[uuid.UUID, list[Franja]] = {}
    for fila in filas:
        agrupadas.setdefault(fila.profesional_id, []).append(
            Franja(
                dia_semana=fila.dia_semana,
                hora_desde=fila.hora_desde,
                hora_hasta=fila.hora_hasta,
            )
        )
    return agrupadas


def _bloqueos(
    filas: list[Bloqueo], profesional: Profesional
) -> list[Intervalo]:
    return [
        Intervalo(inicio=fila.desde, fin=fila.hasta)
        for fila in filas
        if fila.profesional_id in (None, profesional.id)
    ]


def _turnos(filas: list[Turno]) -> dict[uuid.UUID, list[TurnoMetrica]]:
    agrupados: dict[uuid.UUID, list[TurnoMetrica]] = {}
    for fila in filas:
        agrupados.setdefault(fila.profesional_id, []).append(
            TurnoMetrica(inicio=fila.inicio, fin=fila.fin, estado=fila.estado)
        )
    return agrupados


def ocupacion(usuario: Usuario, filtros: ReporteFiltros) -> list[OcupacionProfesional]:
    tz = ZoneInfo(get_settings().tz)
    profesionales, franjas, bloqueos, turnos, _ = _contexto(
        usuario, filtros.desde, filtros.hasta, filtros.profesional_id
    )
    franjas_por = _franjas(franjas)
    turnos_por = _turnos(turnos)
    return [
        OcupacionProfesional(
            profesional_id=profesional.id,
            nombre=profesional.nombre,
            turnos_activos=resumen.turnos_activos,
            minutos_disponibles=resumen.minutos_disponibles,
            minutos_ocupados=resumen.minutos_ocupados,
            ocupacion=resumen.ocupacion,
        )
        for profesional in profesionales
        for resumen in [
            resumen_ocupacion(
                filtros.desde,
                filtros.hasta,
                franjas_por.get(profesional.id, []),
                _bloqueos(bloqueos, profesional),
                turnos_por.get(profesional.id, []),
                tz,
            )
        ]
    ]


def ausencias(usuario: Usuario, filtros: ReporteFiltros) -> list[AusenciasProfesional]:
    profesionales, _, _, turnos, _ = _contexto(
        usuario, filtros.desde, filtros.hasta, filtros.profesional_id
    )
    turnos_por = _turnos(turnos)
    return [
        AusenciasProfesional(
            profesional_id=profesional.id,
            nombre=profesional.nombre,
            atendidos=resumen.atendidos,
            ausentes=resumen.ausentes,
            tasa_ausencia=resumen.tasa_ausencia,
        )
        for profesional in profesionales
        for resumen in [resumen_ausencias(turnos_por.get(profesional.id, []))]
    ]


def recordatorios(usuario: Usuario, filtros: ReporteFiltros) -> list[RecordatoriosProfesional]:
    profesionales, _, _, turnos, enviados = _contexto(
        usuario, filtros.desde, filtros.hasta, filtros.profesional_id
    )
    turnos_por = _turnos(turnos)
    return [
        RecordatoriosProfesional(
            profesional_id=profesional.id,
            nombre=profesional.nombre,
            turnos_confirmados=resumen.confirmados,
            recordatorios_enviados=resumen.enviados,
            ratio=resumen.ratio,
        )
        for profesional in profesionales
        for resumen in [
            resumen_recordatorios(
                confirmados=sum(
                    1
                    for turno in turnos_por.get(profesional.id, [])
                    if turno.estado is EstadoTurno.CONFIRMADO
                ),
                enviados=enviados.get(profesional.id, 0),
            )
        ]
    ]


__all__ = ["ausencias", "ocupacion", "recordatorios"]
