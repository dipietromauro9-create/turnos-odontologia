"""Cálculo puro y determinista de huecos reservables (RN-AG-01, RN-AG-02).

Este módulo no abre sesiones, no ejecuta SQL y no lee un reloj global: recibe
las entidades ya cargadas y un `ahora` inyectado. El servicio de huecos es el
único responsable de las consultas tenant-scoped.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.db.models.turno import EstadoTurno

RANGO_MAXIMO_DIAS = 31
RANGO_MAXIMO = timedelta(days=RANGO_MAXIMO_DIAS)


@dataclass(frozen=True, slots=True)
class Franja:
    """Franja semanal de la plantilla, con horas locales sin zona horaria."""

    dia_semana: int
    hora_desde: time
    hora_hasta: time


@dataclass(frozen=True, slots=True)
class BloqueoIntervalo:
    """Cierre puntual; `profesional_id` nulo representa todo el consultorio."""

    profesional_id: uuid.UUID | None
    desde: datetime
    hasta: datetime


@dataclass(frozen=True, slots=True)
class TurnoIntervalo:
    """Turno ya cargado; solo su intervalo y estado importan al cálculo."""

    profesional_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: EstadoTurno


@dataclass(frozen=True, slots=True)
class Hueco:
    """Intervalo semiabierto reservable, sin ningún dato de paciente (RN-AG-04)."""

    inicio: datetime
    fin: datetime
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID


def _fusionar_franjas(franjas: Sequence[Franja]) -> list[tuple[time, time]]:
    """Une franjas que comparten borde exacto para no inventar un descanso."""
    ordenadas = sorted(franjas, key=lambda franja: franja.hora_desde)
    intervalos: list[tuple[time, time]] = []
    for franja in ordenadas:
        if intervalos and intervalos[-1][1] == franja.hora_desde:
            intervalos[-1] = (intervalos[-1][0], franja.hora_hasta)
        else:
            intervalos.append((franja.hora_desde, franja.hora_hasta))
    return intervalos


def a_zona_local(momento: datetime, tz: ZoneInfo) -> datetime:
    """Normaliza un instante a la zona del consultorio sin leer configuración global."""
    return momento.astimezone(tz)


def _intersecta(
    inicio_a: datetime,
    fin_a: datetime,
    inicio_b: datetime,
    fin_b: datetime,
) -> bool:
    """Intersección semiabierta: compartir solo un borde no es solapar."""
    return inicio_a < fin_b and inicio_b < fin_a


def _franjas_por_dia(disponibilidad: Sequence[Franja]) -> dict[int, list[Franja]]:
    por_dia: dict[int, list[Franja]] = {}
    for franja in disponibilidad:
        por_dia.setdefault(franja.dia_semana, []).append(franja)
    return por_dia


def _intervalos_excluyentes(
    bloqueos: Sequence[BloqueoIntervalo],
    turnos: Sequence[TurnoIntervalo],
    profesional_id: uuid.UUID,
    tz: ZoneInfo,
) -> tuple[list[tuple[datetime, datetime]], list[tuple[datetime, datetime]]]:
    bloqueos_relevantes = [
        (a_zona_local(bloqueo.desde, tz), a_zona_local(bloqueo.hasta, tz))
        for bloqueo in bloqueos
        if bloqueo.profesional_id is None or bloqueo.profesional_id == profesional_id
    ]
    turnos_relevantes = [
        (a_zona_local(turno.inicio, tz), a_zona_local(turno.fin, tz))
        for turno in turnos
        if turno.profesional_id == profesional_id and turno.estado != EstadoTurno.CANCELADO
    ]
    return bloqueos_relevantes, turnos_relevantes


def calcular_huecos(
    *,
    profesional_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    duracion_min: int,
    desde: datetime,
    hasta: datetime,
    disponibilidad: Sequence[Franja],
    bloqueos: Sequence[BloqueoIntervalo] = (),
    turnos: Sequence[TurnoIntervalo] = (),
    ahora: datetime,
    tz: ZoneInfo,
) -> list[Hueco]:
    """Enumera huecos de `duracion_min` anclados al inicio de cada intervalo."""
    desde_local = a_zona_local(desde, tz)
    hasta_local = a_zona_local(hasta, tz)
    ahora_local = a_zona_local(ahora, tz)
    if hasta_local <= desde_local:
        return []

    bloqueos_relevantes, turnos_relevantes = _intervalos_excluyentes(
        bloqueos, turnos, profesional_id, tz
    )
    por_dia = _franjas_por_dia(disponibilidad)
    paso = timedelta(minutes=duracion_min)
    ultimo_dia: date = (hasta_local - timedelta(microseconds=1)).date()
    dia_actual = desde_local.date()
    huecos: list[Hueco] = []

    while dia_actual <= ultimo_dia:
        for inicio_franja, fin_franja in _fusionar_franjas(por_dia.get(dia_actual.weekday(), [])):
            fin_intervalo = datetime.combine(dia_actual, fin_franja, tz)
            cursor = datetime.combine(dia_actual, inicio_franja, tz)
            while cursor + paso <= fin_intervalo:
                fin_candidato = cursor + paso
                if (
                    cursor > ahora_local
                    and desde_local <= cursor < hasta_local
                    and not any(
                        _intersecta(cursor, fin_candidato, inicio, fin)
                        for inicio, fin in bloqueos_relevantes
                    )
                    and not any(
                        _intersecta(cursor, fin_candidato, inicio, fin)
                        for inicio, fin in turnos_relevantes
                    )
                ):
                    huecos.append(Hueco(cursor, fin_candidato, profesional_id, prestacion_id))
                cursor = fin_candidato
        dia_actual += timedelta(days=1)

    huecos.sort(key=lambda hueco: (hueco.inicio, hueco.profesional_id, hueco.prestacion_id))
    return huecos
