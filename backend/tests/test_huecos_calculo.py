"""Cálculo puro de huecos: grilla, bordes y exclusiones sin base de datos."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db.models import EstadoTurno
from app.domain.huecos.calculo import (
    BloqueoIntervalo,
    Franja,
    Hueco,
    TurnoIntervalo,
    calcular_huecos,
)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DIA = date(2030, 6, 3)  # lunes
PROFESIONAL = uuid.uuid4()
PRESTACION = uuid.uuid4()


def franja(
    desde: tuple[int, int],
    hasta: tuple[int, int],
    *,
    dia: date = DIA,
) -> Franja:
    return Franja(
        dia_semana=dia.weekday(),
        hora_desde=time(*desde),
        hora_hasta=time(*hasta),
    )


def instante(dia: date, hora: tuple[int, int]) -> datetime:
    return datetime.combine(dia, time(*hora), TZ)


def calcular(
    franjas: Sequence[Franja],
    *,
    duracion_min: int = 30,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    ahora: datetime | None = None,
    bloqueos: Sequence[BloqueoIntervalo] = (),
    turnos: Sequence[TurnoIntervalo] = (),
) -> list[Hueco]:
    inicio_rango = desde or instante(DIA, (0, 0))
    fin_rango = hasta or instante(DIA + timedelta(days=1), (0, 0))
    referencia = ahora or instante(DIA - timedelta(days=1), (0, 0))
    return calcular_huecos(
        profesional_id=PROFESIONAL,
        prestacion_id=PRESTACION,
        duracion_min=duracion_min,
        desde=inicio_rango,
        hasta=fin_rango,
        disponibilidad=list(franjas),
        bloqueos=list(bloqueos),
        turnos=list(turnos),
        ahora=referencia,
        tz=TZ,
    )


def como_pares(huecos: Sequence[Hueco]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    return [
        (
            (hueco.inicio.hour, hueco.inicio.minute),
            (hueco.fin.hour, hueco.fin.minute),
        )
        for hueco in huecos
    ]


# --- Grupo 2: contrato puro y grilla (RN-AG-01) ---


def test_hueco_alineado_dentro_de_una_franja() -> None:
    huecos = calcular([franja((9, 0), (10, 0))], duracion_min=30)
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]
    assert all(h.profesional_id == PROFESIONAL for h in huecos)
    assert all(h.prestacion_id == PRESTACION for h in huecos)


def test_hueco_que_no_cabe_completo_no_se_ofrece() -> None:
    huecos = calcular([franja((9, 0), (10, 0))], duracion_min=30)
    inicios = [(h.inicio.hour, h.inicio.minute) for h in huecos]
    assert (9, 45) not in inicios
    assert all(h.fin <= instante(DIA, (10, 0)) for h in huecos)


def test_duracion_30_vs_45_cambia_la_grilla() -> None:
    de_30 = calcular([franja((9, 0), (12, 0))], duracion_min=30)
    de_45 = calcular([franja((9, 0), (12, 0))], duracion_min=45)
    assert como_pares(de_30) == [
        ((9, 0), (9, 30)),
        ((9, 30), (10, 0)),
        ((10, 0), (10, 30)),
        ((10, 30), (11, 0)),
        ((11, 0), (11, 30)),
        ((11, 30), (12, 0)),
    ]
    assert como_pares(de_45) == [
        ((9, 0), (9, 45)),
        ((9, 45), (10, 30)),
        ((10, 30), (11, 15)),
        ((11, 15), (12, 0)),
    ]


def test_franjas_contiguas_permiten_un_hueco_que_cruza_el_borde() -> None:
    huecos = calcular(
        [franja((9, 0), (12, 10)), franja((12, 10), (15, 0))],
        duracion_min=30,
    )
    assert ((12, 0), (12, 30)) in como_pares(huecos)


def test_franjas_contiguas_no_inventan_descanso_en_el_borde() -> None:
    huecos = calcular(
        [franja((9, 0), (12, 0)), franja((12, 0), (15, 0))],
        duracion_min=30,
    )
    assert ((11, 30), (12, 0)) in como_pares(huecos)
    assert ((12, 0), (12, 30)) in como_pares(huecos)


def test_descanso_entre_franjas_no_se_rellena() -> None:
    huecos = calcular([franja((9, 0), (10, 0)), franja((10, 15), (11, 0))], duracion_min=30)
    assert como_pares(huecos) == [
        ((9, 0), (9, 30)),
        ((9, 30), (10, 0)),
        ((10, 15), (10, 45)),
    ]
    assert all(not (instante(DIA, (10, 0)) <= h.inicio < instante(DIA, (10, 15))) for h in huecos)


@pytest.mark.parametrize("ahora", [instante(DIA, (9, 0)), instante(DIA, (9, 20))])
def test_inicio_pasado_o_igual_al_presente_se_excluye(ahora: datetime) -> None:
    huecos = calcular([franja((9, 0), (10, 0))], duracion_min=30, ahora=ahora)
    assert como_pares(huecos) == [((9, 30), (10, 0))]


def test_el_rango_de_consulta_es_semiabierto() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        desde=instante(DIA, (9, 0)),
        hasta=instante(DIA, (9, 30)),
    )
    assert como_pares(huecos) == [((9, 0), (9, 30))]


# --- Grupo 2: triangulación de la grilla ---


def test_rango_multi_dia_enumera_cada_dia() -> None:
    dia_siguiente = DIA + timedelta(days=1)
    huecos = calcular(
        [
            franja((9, 0), (10, 0), dia=DIA),
            franja((9, 0), (10, 0), dia=dia_siguiente),
        ],
        duracion_min=30,
        desde=instante(DIA, (0, 0)),
        hasta=instante(DIA + timedelta(days=2), (0, 0)),
    )
    assert [(h.inicio.date(), h.inicio.hour, h.inicio.minute) for h in huecos] == [
        (DIA, 9, 0),
        (DIA, 9, 30),
        (dia_siguiente, 9, 0),
        (dia_siguiente, 9, 30),
    ]


def test_rango_que_empieza_en_medio_de_una_franja_mantiene_el_ancla() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        desde=instante(DIA, (9, 10)),
    )
    assert como_pares(huecos) == [((9, 30), (10, 0))]


def test_rango_que_termina_en_medio_de_una_franja_filtra_por_inicio() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        hasta=instante(DIA, (9, 40)),
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]


def test_dia_sin_disponibilidad_no_genera_huecos() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0), dia=DIA)],
        duracion_min=30,
        desde=instante(DIA, (0, 0)),
        hasta=instante(DIA + timedelta(days=2), (0, 0)),
    )
    assert [h.inicio.date() for h in huecos] == [DIA, DIA]


def test_franja_con_inicio_no_multiplo_de_la_duracion_se_ancla_a_su_inicio() -> None:
    huecos = calcular([franja((9, 7), (10, 0))], duracion_min=30)
    assert como_pares(huecos) == [((9, 7), (9, 37))]


@pytest.mark.parametrize(
    ("duracion", "esperados"),
    [
        (5, 12),
        (15, 4),
        (45, 1),
    ],
)
def test_duraciones_5_15_y_45(duracion: int, esperados: int) -> None:
    huecos = calcular([franja((9, 0), (10, 0))], duracion_min=duracion)
    assert len(huecos) == esperados
    assert huecos[0].inicio == instante(DIA, (9, 0))
    assert huecos[-1].fin <= instante(DIA, (10, 0))


def test_rango_que_cruza_medianoche_enumera_ambos_dias() -> None:
    dia_siguiente = DIA + timedelta(days=1)
    huecos = calcular(
        [
            franja((23, 0), (23, 59), dia=DIA),
            franja((0, 0), (2, 0), dia=dia_siguiente),
        ],
        duracion_min=30,
        desde=instante(DIA, (22, 0)),
        hasta=instante(dia_siguiente, (2, 0)),
    )
    assert [(h.inicio.date(), h.inicio.hour, h.inicio.minute) for h in huecos] == [
        (DIA, 23, 0),
        (dia_siguiente, 0, 0),
        (dia_siguiente, 0, 30),
        (dia_siguiente, 1, 0),
        (dia_siguiente, 1, 30),
    ]


def test_orden_determinista_por_inicio_aunque_las_franjas_lleguen_desordenadas() -> None:
    huecos = calcular(
        [franja((10, 0), (11, 0)), franja((9, 0), (10, 0))],
        duracion_min=30,
    )
    inicios = [h.inicio for h in huecos]
    assert inicios == sorted(inicios)
    assert len(inicios) == len(set(inicios)) == 4


# --- Grupo 3: exclusiones por bloqueos y turnos activos ---


def bloqueo_entre(
    inicio: datetime,
    fin: datetime,
    *,
    profesional: uuid.UUID | None = PROFESIONAL,
) -> BloqueoIntervalo:
    return BloqueoIntervalo(profesional_id=profesional, desde=inicio, hasta=fin)


def turno_entre(
    inicio: datetime,
    fin: datetime,
    *,
    estado: EstadoTurno = EstadoTurno.RESERVADO,
    profesional: uuid.UUID = PROFESIONAL,
) -> TurnoIntervalo:
    return TurnoIntervalo(
        profesional_id=profesional,
        inicio=inicio,
        fin=fin,
        estado=estado,
    )


def test_un_bloqueo_parcial_recorta_la_oferta() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 30))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(instante(DIA, (9, 30)), instante(DIA, (10, 0)))],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((10, 0), (10, 30))]


def test_un_bloqueo_total_deja_la_ventana_sin_huecos() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(instante(DIA, (8, 0)), instante(DIA, (11, 0)))],
    )
    assert huecos == []


def test_un_bloqueo_global_afecta_a_cualquier_profesional() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(instante(DIA, (9, 0)), instante(DIA, (9, 30)), profesional=None)],
    )
    assert como_pares(huecos) == [((9, 30), (10, 0))]


def test_un_bloqueo_de_otro_profesional_no_afecta() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        bloqueos=[
            bloqueo_entre(
                instante(DIA, (9, 0)),
                instante(DIA, (9, 30)),
                profesional=uuid.uuid4(),
            )
        ],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]


@pytest.mark.parametrize(
    "estado",
    [
        EstadoTurno.RESERVADO,
        EstadoTurno.CONFIRMADO,
        EstadoTurno.ATENDIDO,
        EstadoTurno.AUSENTE,
    ],
)
def test_un_turno_activo_ocupa_su_intervalo(estado: EstadoTurno) -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        turnos=[turno_entre(instante(DIA, (9, 0)), instante(DIA, (9, 30)), estado=estado)],
    )
    assert como_pares(huecos) == [((9, 30), (10, 0))]


def test_un_turno_cancelado_libera_el_intervalo() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        turnos=[
            turno_entre(
                instante(DIA, (9, 0)),
                instante(DIA, (9, 30)),
                estado=EstadoTurno.CANCELADO,
            )
        ],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]


def test_un_turno_contiguo_no_excluye_el_hueco() -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        turnos=[turno_entre(instante(DIA, (9, 0)), instante(DIA, (9, 30)))],
    )
    assert ((9, 30), (10, 0)) in como_pares(huecos)


def test_combinacion_de_bloqueo_y_turno() -> None:
    huecos = calcular(
        [franja((9, 0), (11, 0))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(instante(DIA, (9, 30)), instante(DIA, (10, 0)))],
        turnos=[turno_entre(instante(DIA, (10, 30)), instante(DIA, (11, 0)))],
    )
    assert como_pares(huecos) == [
        ((9, 0), (9, 30)),
        ((10, 0), (10, 30)),
    ]


# --- Grupo 3: triangulación de exclusiones ---


def test_varios_bloqueos_solapados_recortan_la_union() -> None:
    huecos = calcular(
        [franja((9, 0), (12, 0))],
        duracion_min=30,
        bloqueos=[
            bloqueo_entre(instante(DIA, (9, 30)), instante(DIA, (10, 30))),
            bloqueo_entre(instante(DIA, (10, 0)), instante(DIA, (11, 0))),
        ],
    )
    assert como_pares(huecos) == [
        ((9, 0), (9, 30)),
        ((11, 0), (11, 30)),
        ((11, 30), (12, 0)),
    ]


def test_un_bloqueo_que_cubre_todo_el_dia_no_deja_huecos() -> None:
    huecos = calcular(
        [franja((9, 0), (12, 0))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(instante(DIA, (0, 0)), instante(DIA, (23, 59)))],
    )
    assert huecos == []


def test_un_turno_que_cruza_medianoche_bloquea_solo_su_intervalo() -> None:
    dia_siguiente = DIA + timedelta(days=1)
    huecos = calcular(
        [
            franja((23, 0), (23, 59), dia=DIA),
            franja((0, 0), (2, 0), dia=dia_siguiente),
        ],
        duracion_min=30,
        desde=instante(DIA, (22, 0)),
        hasta=instante(dia_siguiente, (2, 0)),
        turnos=[turno_entre(instante(DIA, (23, 30)), instante(dia_siguiente, (0, 30)))],
    )
    assert [(h.inicio.date(), h.inicio.hour, h.inicio.minute) for h in huecos] == [
        (DIA, 23, 0),
        (dia_siguiente, 0, 30),
        (dia_siguiente, 1, 0),
        (dia_siguiente, 1, 30),
    ]


@pytest.mark.parametrize(
    "bloqueo",
    [
        (instante(DIA, (8, 0)), instante(DIA, (9, 0))),
        (instante(DIA, (10, 0)), instante(DIA, (11, 0))),
    ],
)
def test_el_borde_exacto_de_un_bloqueo_no_excluye(
    bloqueo: tuple[datetime, datetime],
) -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        bloqueos=[bloqueo_entre(*bloqueo)],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]


@pytest.mark.parametrize(
    "turno",
    [
        (instante(DIA, (8, 0)), instante(DIA, (9, 0))),
        (instante(DIA, (10, 0)), instante(DIA, (11, 0))),
    ],
)
def test_el_borde_exacto_de_un_turno_no_excluye(
    turno: tuple[datetime, datetime],
) -> None:
    huecos = calcular(
        [franja((9, 0), (10, 0))],
        duracion_min=30,
        turnos=[turno_entre(*turno)],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((9, 30), (10, 0))]


def test_bloqueo_global_junto_a_uno_personal_acumulan_sus_efectos() -> None:
    huecos = calcular(
        [franja((9, 0), (11, 0))],
        duracion_min=30,
        bloqueos=[
            bloqueo_entre(
                instante(DIA, (9, 30)),
                instante(DIA, (10, 0)),
                profesional=None,
            ),
            bloqueo_entre(instante(DIA, (10, 0)), instante(DIA, (10, 30))),
        ],
    )
    assert como_pares(huecos) == [((9, 0), (9, 30)), ((10, 30), (11, 0))]
