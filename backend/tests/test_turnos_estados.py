"""Máquina pura, transacción y conservación de datos al transicionar."""

import pytest

from app.core.errors import DomainError
from app.db.models import EstadoTurno, Turno
from app.db.session import tenant_context
from app.domain.turnos.estados import validar_transicion
from app.domain.turnos.service import transicionar
from tests.test_turnos_create import _alta
from tests.test_turnos_create import entorno as entorno
from tests.turnos_factories import AHORA

ARISTAS = {
    (EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO),
    (EstadoTurno.RESERVADO, EstadoTurno.CANCELADO),
    (EstadoTurno.CONFIRMADO, EstadoTurno.ATENDIDO),
    (EstadoTurno.CONFIRMADO, EstadoTurno.CANCELADO),
    (EstadoTurno.CONFIRMADO, EstadoTurno.AUSENTE),
}


@pytest.mark.parametrize("origen", list(EstadoTurno))
@pytest.mark.parametrize("destino", list(EstadoTurno))
def test_maquina_solo_admite_cinco_aristas(origen, destino):
    if (origen, destino) in ARISTAS:
        assert validar_transicion(origen, destino) is None
    else:
        with pytest.raises(DomainError) as exc:
            validar_transicion(origen, destino)
        assert (exc.value.code, exc.value.status_code) == ("RN-TU-04", 422)


@pytest.mark.integration
def test_confirmar_y_atender_preservan_horario_y_codigo(entorno):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        confirmado = transicionar(fila.id, EstadoTurno.CONFIRMADO, entorno.usuario)
        atendido = transicionar(fila.id, EstadoTurno.ATENDIDO, entorno.usuario)
    assert confirmado.estado is EstadoTurno.CONFIRMADO
    assert atendido.estado is EstadoTurno.ATENDIDO
    assert (atendido.inicio, atendido.fin, atendido.codigo_publico) == (
        fila.inicio,
        fila.fin,
        fila.codigo_publico,
    )


@pytest.mark.integration
def test_transicion_invalida_no_modifica_la_fila(entorno, session_factory):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"), pytest.raises(DomainError) as exc:
        transicionar(fila.id, EstadoTurno.ATENDIDO, entorno.usuario)
    assert exc.value.code == "RN-TU-04"
    with session_factory() as session:
        assert session.get(Turno, fila.id).estado is EstadoTurno.RESERVADO


@pytest.mark.integration
def test_cancelar_conserva_fila_y_motivo(entorno, session_factory):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        cancelado = transicionar(
            fila.id,
            EstadoTurno.CANCELADO,
            entorno.usuario,
            motivo_cancelacion="Paciente avisó (ficticio)",
        )
    assert cancelado.motivo_cancelacion == "Paciente avisó (ficticio)"
    with session_factory() as session:
        assert session.get(Turno, fila.id).estado is EstadoTurno.CANCELADO


def fila_en_estado(entorno, estado):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        if estado is EstadoTurno.CANCELADO:
            return transicionar(fila.id, estado, entorno.usuario)
        if estado is not EstadoTurno.RESERVADO:
            fila = transicionar(fila.id, EstadoTurno.CONFIRMADO, entorno.usuario)
        if estado in (EstadoTurno.ATENDIDO, EstadoTurno.AUSENTE):
            fila = transicionar(fila.id, estado, entorno.usuario)
    return fila


def foto(session_factory, identificador):
    with session_factory() as session:
        fila = session.get(Turno, identificador)
        return {c.name: getattr(fila, c.name) for c in Turno.__table__.columns}


@pytest.mark.integration
@pytest.mark.parametrize("origen", list(EstadoTurno))
@pytest.mark.parametrize("destino", list(EstadoTurno))
def test_los_25_pares_persistidos_y_snapshot_de_rechazo(entorno, session_factory, origen, destino):
    fila = fila_en_estado(entorno, origen)
    antes = foto(session_factory, fila.id)
    with tenant_context(entorno.tenant.id, "demo"):
        if (origen, destino) in ARISTAS:
            nuevo = transicionar(fila.id, destino, entorno.usuario)
            assert nuevo.estado is destino
        else:
            with pytest.raises(DomainError) as exc:
                transicionar(fila.id, destino, entorno.usuario)
            assert exc.value.code == "RN-TU-04"
    despues = foto(session_factory, fila.id)
    if (origen, destino) not in ARISTAS:
        assert despues == antes
    else:
        assert {k: v for k, v in despues.items() if k not in {"estado", "actualizado_en"}} == {
            k: v for k, v in antes.items() if k not in {"estado", "actualizado_en"}
        }


@pytest.mark.integration
@pytest.mark.parametrize("motivo", [None, "", "Cambio ficticio"])
def test_motivo_cancelacion_opcional_no_exige_texto(entorno, motivo):
    fila = _alta(entorno)
    with tenant_context(entorno.tenant.id, "demo"):
        cancelado = transicionar(
            fila.id, EstadoTurno.CANCELADO, entorno.usuario, motivo_cancelacion=motivo
        )
    assert cancelado.motivo_cancelacion == motivo


@pytest.mark.integration
@pytest.mark.parametrize("estado", [EstadoTurno.CANCELADO, EstadoTurno.AUSENTE])
def test_cancelado_libera_ausente_sigue_ocupando(entorno, estado):
    from app.domain.turnos.schemas import TurnoCreate
    from app.domain.turnos.service import crear

    fila_en_estado(entorno, estado)
    with tenant_context(entorno.tenant.id, "demo"):
        if estado is EstadoTurno.CANCELADO:
            assert (
                crear(TurnoCreate(**entorno.datos()), entorno.usuario, ahora=AHORA).id is not None
            )
        else:
            with pytest.raises(DomainError) as exc:
                crear(TurnoCreate(**entorno.datos()), entorno.usuario, ahora=AHORA)
            assert exc.value.code == "RN-TU-01"


@pytest.mark.integration
def test_cancelacion_concurrente_impide_confirmacion_obsoleta(
    entorno, session_factory, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local

    from app.domain.turnos.repository import TurnosRepository

    fila = _alta(entorno)
    primero_bloqueado, segundo_intenta = Event(), Event()
    hilo = local()
    original = TurnosRepository.obtener_bloqueado
    observados = []

    def obtener(self, identificador):
        if hilo.indice == 0:
            resultado = original(self, identificador)
            primero_bloqueado.set()
            assert segundo_intenta.wait(timeout=10)
            return resultado
        assert primero_bloqueado.wait(timeout=10)
        segundo_intenta.set()
        resultado = original(self, identificador)
        observados.append(resultado.estado)
        return resultado

    monkeypatch.setattr(TurnosRepository, "obtener_bloqueado", obtener)

    def operar(indice):
        hilo.indice = indice
        with tenant_context(entorno.tenant.id, "demo"):
            try:
                destino = EstadoTurno.CANCELADO if indice == 0 else EstadoTurno.CONFIRMADO
                return transicionar(fila.id, destino, entorno.usuario).estado.value
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(operar, [0, 1]))
    assert resultados == ["cancelado", "RN-TU-04"]
    assert observados == [EstadoTurno.CANCELADO]
    assert foto(session_factory, fila.id)["estado"] is EstadoTurno.CANCELADO
