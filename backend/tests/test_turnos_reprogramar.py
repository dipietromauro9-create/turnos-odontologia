"""Reprogramación in situ: identidad/duración congeladas y rollback real."""

from datetime import timedelta

import pytest

from app.core.errors import DomainError
from app.db.models import Bloqueo, EstadoTurno, Prestacion, Turno
from app.db.session import tenant_context
from app.domain.turnos.service import reprogramar
from tests.test_turnos_create import _alta
from tests.test_turnos_create import entorno as entorno
from tests.test_turnos_estados import fila_en_estado, foto
from tests.turnos_factories import AHORA, INICIO

pytestmark = pytest.mark.integration


def test_mover_conserva_identidad_estado_codigo_y_duracion(entorno, session_factory):
    original = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        movido = reprogramar(original.id, INICIO + timedelta(hours=1), entorno.usuario, ahora=AHORA)
    assert (movido.id, movido.codigo_publico, movido.estado) == (
        original.id,
        original.codigo_publico,
        original.estado,
    )
    assert movido.inicio == INICIO + timedelta(hours=1)
    assert movido.fin - movido.inicio == original.fin - original.inicio
    with session_factory() as session:
        assert session.query(Turno).count() == 1


def test_destino_ocupado_no_cancela_ni_mueve_original(entorno, session_factory):
    original = _alta(entorno)
    _alta(entorno, inicio=INICIO + timedelta(hours=1))
    antes = foto(session_factory, original.id)
    with tenant_context(entorno.tenant.id, "demo"), pytest.raises(DomainError) as exc:
        reprogramar(original.id, INICIO + timedelta(hours=1), entorno.usuario, ahora=AHORA)
    assert exc.value.code == "RN-TU-01"
    assert foto(session_factory, original.id) == antes
    with session_factory() as session:
        assert session.query(Turno).count() == 2


@pytest.mark.parametrize("estado", [EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO])
def test_reprogramar_conserva_estado_y_duracion_aunque_cambie_catalogo(
    entorno, session_factory, estado
):
    fila = fila_en_estado(entorno, estado)
    with session_factory() as session:
        session.get(Prestacion, entorno.prestacion.id).duracion_min = 60
        session.commit()
    with tenant_context(entorno.tenant.id, "demo"):
        movido = reprogramar(fila.id, INICIO + timedelta(hours=1), entorno.usuario, ahora=AHORA)
    assert movido.fin - movido.inicio == timedelta(minutes=30)
    assert movido.estado is estado and movido.codigo_publico == fila.codigo_publico
    assert (movido.profesional_id, movido.paciente_id, movido.prestacion_id) == (
        fila.profesional_id,
        fila.paciente_id,
        fila.prestacion_id,
    )


def test_interseccion_con_el_propio_intervalo_no_es_ocupacion(entorno):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        movido = reprogramar(fila.id, INICIO + timedelta(minutes=15), entorno.usuario, ahora=AHORA)
    assert movido.inicio == INICIO + timedelta(minutes=15)


@pytest.mark.parametrize("caso", ["plantilla", "pasado", "bloqueo_global", "bloqueo_personal"])
def test_destino_invalido_restaura_snapshot_completo(entorno, session_factory, caso):
    fila = _alta(entorno)
    destino = INICIO + timedelta(hours=1)
    code = "RN-AG-01"
    if caso == "plantilla":
        destino = INICIO.replace(hour=18)
    elif caso == "pasado":
        destino = AHORA
    else:
        code = "RN-AG-02"
        with session_factory() as session:
            session.add(
                Bloqueo(
                    tenant_id=entorno.tenant.id,
                    profesional_id=entorno.profesional.id if caso == "bloqueo_personal" else None,
                    desde=destino,
                    hasta=destino + timedelta(minutes=15),
                    motivo="Ficticio",
                )
            )
            session.commit()
    antes = foto(session_factory, fila.id)
    with tenant_context(entorno.tenant.id, "demo"), pytest.raises(DomainError) as exc:
        reprogramar(fila.id, destino, entorno.usuario, ahora=AHORA)
    assert exc.value.code == code
    assert foto(session_factory, fila.id) == antes


@pytest.mark.parametrize(
    "estado", [EstadoTurno.ATENDIDO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE]
)
def test_terminales_no_se_reprograman(entorno, session_factory, estado):
    fila = fila_en_estado(entorno, estado)
    antes = foto(session_factory, fila.id)
    with tenant_context(entorno.tenant.id, "demo"), pytest.raises(DomainError) as exc:
        reprogramar(fila.id, INICIO + timedelta(hours=1), entorno.usuario, ahora=AHORA)
    assert exc.value.code == "RN-TU-04"
    assert foto(session_factory, fila.id) == antes


def test_sobreturno_conserva_excepcion_y_motivo_al_moverse(entorno):
    fila = _alta(
        entorno,
        inicio=INICIO.replace(hour=18),
        es_sobreturno=True,
        motivo_sobreturno="Urgencia ficticia",
    )
    with tenant_context(entorno.tenant.id, "demo"):
        movido = reprogramar(fila.id, INICIO.replace(hour=19), entorno.usuario, ahora=AHORA)
    assert movido.estado is EstadoTurno.CONFIRMADO and movido.es_sobreturno
    assert movido.motivo_sobreturno == "Urgencia ficticia"


def test_carrera_reserva_ganadora_revierte_reprogramacion(entorno, session_factory, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event

    from app.domain.turnos.repository import TurnosRepository

    fila = _alta(entorno)
    antes = foto(session_factory, fila.id)
    destino = INICIO + timedelta(hours=1)
    barrera, reserva_hecha = Barrier(2), Event()
    original = TurnosRepository.ocupado

    def consultar(self, profesional_id, inicio, fin, excluir=None):
        resultado = original(self, profesional_id, inicio, fin, excluir)
        assert resultado is False
        barrera.wait(timeout=10)
        if excluir is not None:
            assert reserva_hecha.wait(timeout=10)
        return resultado

    monkeypatch.setattr(TurnosRepository, "ocupado", consultar)

    def reservar():
        try:
            _alta(entorno, inicio=destino)
            return "creado"
        finally:
            reserva_hecha.set()

    def mover():
        with tenant_context(entorno.tenant.id, "demo"):
            try:
                reprogramar(fila.id, destino, entorno.usuario, ahora=AHORA)
                return "movido"
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        intento = pool.submit(mover)
        ganador = pool.submit(reservar)
        assert ganador.result(timeout=20) == "creado"
        assert intento.result(timeout=20) == "RN-TU-01"
    assert foto(session_factory, fila.id) == antes
    with session_factory() as session:
        assert session.query(Turno).count() == 2
