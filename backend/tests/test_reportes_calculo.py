"""Cálculo puro de ocupación, ausencias e IN-03 (RN-RP-01)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db.models import EstadoTurno
from app.domain.reportes.calculo import (
    Franja,
    Intervalo,
    TurnoMetrica,
    resumen_ausencias,
    resumen_ocupacion,
    resumen_recordatorios,
)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DIA = date(2030, 6, 3)
INICIO_DIA = datetime.combine(DIA, time(0), tzinfo=TZ)
FIN_DIA = INICIO_DIA + timedelta(days=1)


def _franja(desde: time = time(9), hasta: time = time(13)) -> Franja:
    return Franja(dia_semana=DIA.weekday(), hora_desde=desde, hora_hasta=hasta)


def _turno(
    hora: int, minutos: int = 30, estado: EstadoTurno = EstadoTurno.CONFIRMADO
) -> TurnoMetrica:
    inicio = datetime.combine(DIA, time(hora), tzinfo=TZ)
    return TurnoMetrica(inicio=inicio, fin=inicio + timedelta(minutes=minutos), estado=estado)


def test_ocupacion_por_minutos_con_turnos_activos() -> None:
    resumen = resumen_ocupacion(
        INICIO_DIA,
        FIN_DIA,
        [_franja()],
        [],
        [_turno(9), _turno(10, estado=EstadoTurno.ATENDIDO)],
        TZ,
    )
    assert resumen.minutos_disponibles == 240
    assert resumen.minutos_ocupados == 60
    assert resumen.turnos_activos == 2
    assert resumen.ocupacion == pytest.approx(0.25)


def test_un_turno_ausente_sigue_ocupando() -> None:
    resumen = resumen_ocupacion(
        INICIO_DIA, FIN_DIA, [_franja()], [], [_turno(9, estado=EstadoTurno.AUSENTE)], TZ
    )
    assert resumen.minutos_ocupados == 30
    assert resumen.turnos_activos == 1


def test_un_turno_cancelado_libera_el_hueco() -> None:
    resumen = resumen_ocupacion(
        INICIO_DIA, FIN_DIA, [_franja()], [], [_turno(9, estado=EstadoTurno.CANCELADO)], TZ
    )
    assert resumen.minutos_ocupados == 0
    assert resumen.turnos_activos == 0
    assert resumen.ocupacion == 0


def test_un_bloqueo_reduce_la_capacidad() -> None:
    bloqueo = Intervalo(
        inicio=datetime.combine(DIA, time(10), tzinfo=TZ),
        fin=datetime.combine(DIA, time(11), tzinfo=TZ),
    )
    resumen = resumen_ocupacion(INICIO_DIA, FIN_DIA, [_franja()], [bloqueo], [], TZ)
    assert resumen.minutos_disponibles == 180


def test_sin_franjas_la_ocupacion_es_cero() -> None:
    resumen = resumen_ocupacion(INICIO_DIA, FIN_DIA, [], [], [_turno(9)], TZ)
    assert resumen.minutos_disponibles == 0
    assert resumen.ocupacion == 0


def test_turno_que_empieza_antes_del_rango_queda_excluido() -> None:
    previo = TurnoMetrica(
        inicio=INICIO_DIA - timedelta(minutes=15),
        fin=INICIO_DIA + timedelta(minutes=15),
        estado=EstadoTurno.CONFIRMADO,
    )
    resumen = resumen_ocupacion(INICIO_DIA, FIN_DIA, [_franja()], [], [previo], TZ)
    assert resumen.turnos_activos == 0 and resumen.minutos_ocupados == 0


def test_el_rango_recorta_la_ocupacion_y_la_capacidad() -> None:
    desde = datetime.combine(DIA, time(9), tzinfo=TZ)
    hasta = datetime.combine(DIA, time(12), tzinfo=TZ)
    resumen = resumen_ocupacion(
        desde, hasta, [_franja()], [], [_turno(9, minutos=120), _turno(11, minutos=120)], TZ
    )
    assert resumen.minutos_disponibles == 180
    assert resumen.minutos_ocupados == 180


def test_sobreturnos_pueden_superar_la_capacidad() -> None:
    resumen = resumen_ocupacion(
        INICIO_DIA,
        FIN_DIA,
        [_franja(desde=time(9), hasta=time(10))],
        [],
        [_turno(9), _turno(9)],
        TZ,
    )
    assert resumen.minutos_disponibles == 60
    assert resumen.minutos_ocupados == 60
    assert resumen.ocupacion == 1.0


def test_dos_franjas_contiguas_no_inventan_descanso() -> None:
    franjas = [_franja(time(9), time(13)), _franja(time(13), time(17))]
    resumen = resumen_ocupacion(INICIO_DIA, FIN_DIA, franjas, [], [], TZ)
    assert resumen.minutos_disponibles == 480


def test_tasa_de_ausencia() -> None:
    resumen = resumen_ausencias(
        [
            _turno(9, estado=EstadoTurno.ATENDIDO),
            _turno(10, estado=EstadoTurno.ATENDIDO),
            _turno(11, estado=EstadoTurno.ATENDIDO),
            _turno(12, estado=EstadoTurno.AUSENTE),
            _turno(13, estado=EstadoTurno.CONFIRMADO),
        ]
    )
    assert resumen.atendidos == 3 and resumen.ausentes == 1
    assert resumen.tasa_ausencia == pytest.approx(0.25)


def test_sin_turnos_cerrados_la_tasa_es_cero() -> None:
    resumen = resumen_ausencias([_turno(9, estado=EstadoTurno.CONFIRMADO)])
    assert resumen.tasa_ausencia == 0


def test_ratio_in_03() -> None:
    resumen = resumen_recordatorios(confirmados=4, enviados=3)
    assert resumen.ratio == pytest.approx(0.75)


def test_ratio_in_03_sin_confirmados() -> None:
    assert resumen_recordatorios(confirmados=0, enviados=2).ratio == 0
