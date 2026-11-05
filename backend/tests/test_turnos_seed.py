"""Seed ficticio por servicio: tres ejemplos estables e idempotentes."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.db.models import Bloqueo, EstadoTurno, Paciente, Prestacion, Profesional, Turno, Usuario
from app.db.seed import run_seed
from app.db.session import tenant_context
from app.domain.turnos.service import reprogramar, transicionar
from tests.factories import crear_prestacion
from tests.turnos_factories import entorno_turnos

pytestmark = pytest.mark.integration


def snapshot(session_factory):
    with session_factory() as session:
        return {
            fila.id: tuple(getattr(fila, c.name) for c in Turno.__table__.columns)
            for fila in session.execute(select(Turno)).scalars()
        }


def test_primer_seed_crea_tres_turnos_por_servicio(app_env, session_factory):
    resultado = run_seed()
    with session_factory() as session:
        filas = list(session.execute(select(Turno).order_by(Turno.inicio)).scalars())
    assert len(filas) == 3
    assert {fila.estado for fila in filas} == {
        EstadoTurno.RESERVADO,
        EstadoTurno.CONFIRMADO,
        EstadoTurno.ATENDIDO,
    }
    assert resultado["turnos_creados"] == 3
    assert len({fila.codigo_publico for fila in filas}) == 3
    assert all(fila.fin - fila.inicio == timedelta(minutes=30) for fila in filas)
    assert all(a.fin <= b.inicio for a, b in zip(filas, filas[1:], strict=False))


def test_segundo_seed_no_duplica_ni_cambia_fechas_codigos_estados(app_env, session_factory):
    run_seed()
    antes = snapshot(session_factory)
    resultado = run_seed()
    assert len(antes) == 3
    assert resultado["turnos_creados"] == 0
    assert snapshot(session_factory) == antes


def test_seed_respeta_cancelacion_y_reprogramacion_manuales(app_env, session_factory):
    run_seed()
    with session_factory() as session:
        filas = {fila.estado: fila for fila in session.execute(select(Turno)).scalars()}
        usuario = session.execute(select(Usuario).where(Usuario.email == "dueno@demo")).scalar_one()
    assert len(filas) == 3
    reservado, confirmado = filas[EstadoTurno.RESERVADO], filas[EstadoTurno.CONFIRMADO]
    with tenant_context(usuario.tenant_id, "demo"):
        transicionar(
            reservado.id, EstadoTurno.CANCELADO, usuario, motivo_cancelacion="Cambio ficticio"
        )
        reprogramar(confirmado.id, confirmado.inicio + timedelta(days=14), usuario)
    antes = snapshot(session_factory)
    assert run_seed()["turnos_creados"] == 0
    assert snapshot(session_factory) == antes


def test_seed_no_siembra_turnos_en_otro_tenant(app_env, session_factory):
    with session_factory() as session:
        otro = entorno_turnos(session, "otro")
    run_seed()
    with session_factory() as session:
        assert (
            list(session.execute(select(Turno).where(Turno.tenant_id == otro.tenant.id)).scalars())
            == []
        )
        assert session.get(Paciente, otro.paciente.id).nombre == otro.paciente.nombre


@pytest.mark.parametrize(
    "caso", ["profesional_inactivo", "prestacion_inactiva", "duracion_extensa", "bloqueo"]
)
def test_ejemplos_nuevos_se_omiten_si_catalogo_o_agenda_no_permiten(app_env, session_factory, caso):
    run_seed()
    with session_factory() as session:
        anteriores = list(session.execute(select(Turno).order_by(Turno.inicio)).scalars())
        tenant_id = anteriores[0].tenant_id
        # Simula catálogo de C-06 sin ejemplos de C-07 en esta DB exclusiva.
        session.execute(delete(Turno).where(Turno.tenant_id == tenant_id))
        if caso == "profesional_inactivo":
            session.get(Profesional, anteriores[0].profesional_id).activo = False
        elif caso == "prestacion_inactiva":
            session.get(Prestacion, anteriores[0].prestacion_id).activa = False
        elif caso == "duracion_extensa":
            session.get(Prestacion, anteriores[0].prestacion_id).duracion_min = 480
        else:
            session.add(
                Bloqueo(
                    tenant_id=tenant_id,
                    profesional_id=None,
                    desde=anteriores[0].inicio - timedelta(hours=1),
                    hasta=anteriores[-1].fin + timedelta(hours=1),
                    motivo="Cierre ficticio",
                )
            )
        session.commit()
    resultado = run_seed()
    assert resultado["turnos_creados"] == 0 and resultado["turnos_omitidos"] == 3
    assert snapshot(session_factory) == {}


def test_catalogo_inactivo_no_modifica_ejemplos_ya_existentes(app_env, session_factory):
    run_seed()
    antes = snapshot(session_factory)
    with session_factory() as session:
        fila = session.execute(select(Turno)).scalars().first()
        session.get(Profesional, fila.profesional_id).activo = False
        session.get(Prestacion, fila.prestacion_id).activa = False
        session.commit()
    resultado = run_seed()
    assert resultado["turnos_creados"] == resultado["turnos_omitidos"] == 0
    assert snapshot(session_factory) == antes


def test_ejemplos_referencian_solo_pacientes_ficticios_documentados(app_env, session_factory):
    run_seed()
    with session_factory() as session:
        filas = list(session.execute(select(Turno)).scalars())
        for fila in filas:
            paciente = session.get(Paciente, fila.paciente_id)
            assert paciente.nombre.startswith("Paciente Demo")
            assert paciente.telefono in {"1145550001", "1145550002"}
            assert paciente.documento is None and paciente.fecha_nac is None


@pytest.mark.parametrize("faltan_ejemplos", [False, True])
def test_consultas_duplicadas_validas_no_rompen_seed(app_env, session_factory, faltan_ejemplos):
    run_seed()
    antes = snapshot(session_factory)
    with session_factory() as session:
        fila = session.execute(select(Turno)).scalars().first()
        from app.db.models import Tenant

        tenant = session.get(Tenant, fila.tenant_id)
        crear_prestacion(session, tenant, nombre="Consulta", duracion_min=45)
        if faltan_ejemplos:
            session.execute(delete(Turno).where(Turno.tenant_id == tenant.id))
            session.commit()
    resultado = run_seed()
    if faltan_ejemplos:
        assert resultado["turnos_creados"] == 3
        with session_factory() as session:
            assert all(
                t.fin - t.inicio == timedelta(minutes=30)
                for t in session.execute(select(Turno)).scalars()
            )
    else:
        assert resultado["turnos_creados"] == 0
        assert snapshot(session_factory) == antes


def test_consulta_duplicada_activa_se_prefiere_a_la_inactiva(app_env, session_factory):
    run_seed()
    with session_factory() as session:
        from app.db.models import Tenant

        fila = session.execute(select(Turno)).scalars().first()
        tenant = session.get(Tenant, fila.tenant_id)
        session.get(Prestacion, fila.prestacion_id).activa = False
        nueva = crear_prestacion(session, tenant, nombre="Consulta", duracion_min=45)
        session.execute(delete(Turno).where(Turno.tenant_id == tenant.id))
        session.commit()
    assert run_seed()["turnos_creados"] == 3
    with session_factory() as session:
        filas = list(session.execute(select(Turno)).scalars())
        assert {fila.prestacion_id for fila in filas} == {nueva.id}
        assert all(fila.fin - fila.inicio == timedelta(minutes=45) for fila in filas)
