"""Cálculo puro y determinista de reportes (RN-RP-01, IN-03).

Sin I/O, sin sesiones y sin reloj global: recibe los datos ya cargados por el
repositorio de reportes y la zona horaria del sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.db.models import EstadoTurno


@dataclass(frozen=True, slots=True)
class Franja:
    """Franja semanal de la plantilla, en horas locales sin zona."""

    dia_semana: int
    hora_desde: time
    hora_hasta: time


@dataclass(frozen=True, slots=True)
class Intervalo:
    """Bloqueo o cierre puntual ya normalizado a instantes con zona."""

    inicio: datetime
    fin: datetime


@dataclass(frozen=True, slots=True)
class TurnoMetrica:
    """Turno ya cargado; solo el intervalo y el estado importan al cálculo."""

    inicio: datetime
    fin: datetime
    estado: EstadoTurno


@dataclass(frozen=True, slots=True)
class ResumenOcupacion:
    turnos_activos: int
    minutos_disponibles: int
    minutos_ocupados: int
    ocupacion: float


@dataclass(frozen=True, slots=True)
class ResumenAusencias:
    atendidos: int
    ausentes: int
    tasa_ausencia: float


@dataclass(frozen=True, slots=True)
class ResumenRecordatorios:
    confirmados: int
    enviados: int
    ratio: float


def _minutos(inicio: datetime, fin: datetime) -> int:
    return int((fin - inicio).total_seconds() // 60)


def _recortar(
    inicio: datetime, fin: datetime, desde: datetime, hasta: datetime
) -> tuple[datetime, datetime]:
    return max(inicio, desde), min(fin, hasta)


def _fusionar(intervalos: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    fusionados: list[tuple[datetime, datetime]] = []
    for inicio, fin in sorted(intervalos):
        if fusionados and inicio <= fusionados[-1][1]:
            fusionados[-1] = (fusionados[-1][0], max(fusionados[-1][1], fin))
        else:
            fusionados.append((inicio, fin))
    return fusionados


def _restar(
    disponibles: list[tuple[datetime, datetime]],
    bloqueos: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not bloqueos:
        return disponibles
    resultado: list[tuple[datetime, datetime]] = []
    for inicio, fin in disponibles:
        segmentos = [(inicio, fin)]
        for bloqueo_inicio, bloqueo_fin in _fusionar(bloqueos):
            nuevos: list[tuple[datetime, datetime]] = []
            for segmento_inicio, segmento_fin in segmentos:
                if bloqueo_fin <= segmento_inicio or bloqueo_inicio >= segmento_fin:
                    nuevos.append((segmento_inicio, segmento_fin))
                    continue
                if bloqueo_inicio > segmento_inicio:
                    nuevos.append((segmento_inicio, bloqueo_inicio))
                if bloqueo_fin < segmento_fin:
                    nuevos.append((bloqueo_fin, segmento_fin))
            segmentos = nuevos
        resultado.extend(segmentos)
    return resultado


def _intervalos_disponibles(
    desde: datetime,
    hasta: datetime,
    franjas: list[Franja],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    desde_local = desde.astimezone(tz)
    hasta_local = hasta.astimezone(tz)
    ultimo: date = (hasta_local - timedelta(microseconds=1)).date()
    dia = desde_local.date()
    intervalos: list[tuple[datetime, datetime]] = []
    while dia <= ultimo:
        for franja in franjas:
            if franja.dia_semana != dia.weekday():
                continue
            inicio = datetime.combine(dia, franja.hora_desde, tzinfo=tz)
            fin = datetime.combine(dia, franja.hora_hasta, tzinfo=tz)
            recortado = _recortar(inicio, fin, desde, hasta)
            if recortado[1] > recortado[0]:
                intervalos.append(recortado)
        dia += timedelta(days=1)
    return intervalos


def minutos_disponibles(
    desde: datetime,
    hasta: datetime,
    franjas: list[Franja],
    bloqueos: list[Intervalo],
    tz: ZoneInfo,
) -> int:
    """Capacidad neta del período: plantilla menos bloqueos, recortada al rango."""
    disponibles = _intervalos_disponibles(desde, hasta, franjas, tz)
    netos = _restar(disponibles, [(b.inicio, b.fin) for b in bloqueos])
    return sum(_minutos(inicio, fin) for inicio, fin in netos)


def _turnos_en_rango(
    turnos: list[TurnoMetrica], desde: datetime, hasta: datetime
) -> list[TurnoMetrica]:
    return [turno for turno in turnos if desde <= turno.inicio < hasta]


def resumen_ocupacion(
    desde: datetime,
    hasta: datetime,
    franjas: list[Franja],
    bloqueos: list[Intervalo],
    turnos: list[TurnoMetrica],
    tz: ZoneInfo,
) -> ResumenOcupacion:
    """Ocupación = minutos de turnos activos / minutos disponibles (RN-RP-01)."""
    en_rango = _turnos_en_rango(turnos, desde, hasta)
    activos = [turno for turno in en_rango if turno.estado is not EstadoTurno.CANCELADO]
    disponibles = minutos_disponibles(desde, hasta, franjas, bloqueos, tz)
    ocupados = 0
    for turno in activos:
        inicio, fin = _recortar(turno.inicio, turno.fin, desde, hasta)
        if fin > inicio:
            ocupados += _minutos(inicio, fin)
    return ResumenOcupacion(
        turnos_activos=len(activos),
        minutos_disponibles=disponibles,
        minutos_ocupados=ocupados,
        ocupacion=(ocupados / disponibles) if disponibles else 0.0,
    )


def resumen_ausencias(turnos: list[TurnoMetrica]) -> ResumenAusencias:
    """Ausencias = ausente / (atendido + ausente); 0 sin turnos cerrados."""
    atendidos = sum(1 for turno in turnos if turno.estado is EstadoTurno.ATENDIDO)
    ausentes = sum(1 for turno in turnos if turno.estado is EstadoTurno.AUSENTE)
    denominador = atendidos + ausentes
    return ResumenAusencias(
        atendidos=atendidos,
        ausentes=ausentes,
        tasa_ausencia=(ausentes / denominador) if denominador else 0.0,
    )


def resumen_recordatorios(confirmados: int, enviados: int) -> ResumenRecordatorios:
    """IN-03: recordatorios enviados / turnos confirmados; 0 sin confirmados."""
    return ResumenRecordatorios(
        confirmados=confirmados,
        enviados=enviados,
        ratio=(enviados / confirmados) if confirmados else 0.0,
    )


__all__ = [
    "Franja",
    "Intervalo",
    "ResumenAusencias",
    "ResumenOcupacion",
    "ResumenRecordatorios",
    "TurnoMetrica",
    "minutos_disponibles",
    "resumen_ausencias",
    "resumen_ocupacion",
    "resumen_recordatorios",
]
