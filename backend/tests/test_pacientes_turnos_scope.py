"""El vínculo asistencial concede y revoca ficha por todas sus vías."""

from dataclasses import dataclass
from datetime import time, timedelta

import pytest

from app.core.errors import DomainError
from app.db.models import (
    Disponibilidad,
    EstadoTurno,
    Paciente,
    Profesional,
    RolUsuario,
    Turno,
    Usuario,
)
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.dependencies import AlcancePacientes
from app.domain.pacientes.schemas import PacienteCreate, PacienteUpdate
from app.domain.pacientes.service import (
    actualizar_paciente,
    buscar_pacientes,
    crear_o_reutilizar_paciente,
    crear_paciente,
    obtener_paciente,
)
from app.domain.turnos.schemas import TurnoCreate
from app.domain.turnos.service import crear, transicionar
from tests.factories import crear_profesional, crear_usuario
from tests.turnos_factories import AHORA, INICIO, EntornoTurnos, entorno_turnos

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class EntornoScope:
    base: EntornoTurnos
    usuario: Usuario
    profesional: Profesional


@pytest.fixture()
def entorno(app_env, session_factory):
    with session_factory() as session:
        base = entorno_turnos(session)
        usuario = crear_usuario(session, base.tenant, "pro@demo", RolUsuario.PROFESIONAL)
        profesional = crear_profesional(session, base.tenant, usuario=usuario)
        session.add(
            Disponibilidad(
                tenant_id=base.tenant.id,
                profesional_id=profesional.id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(13),
            )
        )
        session.commit()
        return EntornoScope(base, usuario, profesional)


def asignar(entorno, estado, **cambios):
    base = entorno.base
    with tenant_context(base.tenant.id, "demo"):
        fila = crear(
            TurnoCreate(**base.datos(profesional_id=entorno.profesional.id, **cambios)),
            base.usuario,
            ahora=AHORA,
        )
        if estado is EstadoTurno.CANCELADO:
            return transicionar(fila.id, estado, base.usuario)
        if estado is not EstadoTurno.RESERVADO:
            fila = transicionar(fila.id, EstadoTurno.CONFIRMADO, base.usuario)
        if estado in (EstadoTurno.ATENDIDO, EstadoTurno.AUSENTE):
            fila = transicionar(fila.id, estado, base.usuario)
    return fila


@pytest.mark.parametrize("estado", [EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO])
def test_asignacion_pendiente_habilita_ficha_edicion_y_busqueda(entorno, estado):
    asignar(entorno, estado)
    with (
        tenant_context(entorno.base.tenant.id, "demo"),
        tenant_session(entorno.base.tenant.id) as session,
    ):
        paciente = obtener_paciente(session, entorno.base.paciente.id, entorno.usuario)
        editado = actualizar_paciente(
            session, paciente.id, PacienteUpdate(observaciones="Atención"), entorno.usuario
        )
        encontrados = buscar_pacientes(
            session, q="Ficticio", alcance=AlcancePacientes.PROPIOS, usuario_id=entorno.usuario.id
        )
        session.commit()
    assert editado.observaciones == "Atención"
    assert [p.id for p in encontrados] == [entorno.base.paciente.id]


@pytest.mark.parametrize("estado", [EstadoTurno.CANCELADO, EstadoTurno.AUSENTE])
def test_terminal_sin_atencion_no_habilita_ficha(entorno, estado):
    asignar(entorno, estado)
    with (
        tenant_context(entorno.base.tenant.id, "demo"),
        tenant_session(entorno.base.tenant.id) as session,
    ):
        with pytest.raises(DomainError) as exc:
            obtener_paciente(session, entorno.base.paciente.id, entorno.usuario)
        assert (exc.value.code, exc.value.status_code) == ("RN-AU-03", 403)
        assert (
            buscar_pacientes(
                session, alcance=AlcancePacientes.PROPIOS, usuario_id=entorno.usuario.id
            )
            == []
        )


def _visible(entorno, usuario=None):
    usuario = usuario or entorno.usuario
    with (
        tenant_context(entorno.base.tenant.id, "demo"),
        tenant_session(entorno.base.tenant.id) as session,
    ):
        return obtener_paciente(session, entorno.base.paciente.id, usuario)


def _assert_sin_ficha(entorno, session_factory):
    with (
        tenant_context(entorno.base.tenant.id, "demo"),
        tenant_session(entorno.base.tenant.id) as session,
    ):
        for q in (None, "Ficticio", "114555"):
            assert (
                buscar_pacientes(
                    session, q=q, alcance=AlcancePacientes.PROPIOS, usuario_id=entorno.usuario.id
                )
                == []
            )
        for accion in ("leer", "editar"):
            with pytest.raises(DomainError) as exc:
                if accion == "leer":
                    obtener_paciente(session, entorno.base.paciente.id, entorno.usuario)
                else:
                    actualizar_paciente(
                        session,
                        entorno.base.paciente.id,
                        PacienteUpdate(observaciones="No permitido"),
                        entorno.usuario,
                    )
            assert (exc.value.code, exc.value.status_code) == ("RN-AU-03", 403)
    with session_factory() as session:
        assert session.get(Paciente, entorno.base.paciente.id).observaciones is None


@pytest.mark.parametrize("destino", [EstadoTurno.CANCELADO, EstadoTurno.AUSENTE])
def test_ultima_cita_pendiente_revoca_todas_las_vias(entorno, session_factory, destino):
    fila = asignar(entorno, EstadoTurno.CONFIRMADO)
    assert _visible(entorno).id == entorno.base.paciente.id
    with tenant_context(entorno.base.tenant.id, "demo"):
        transicionar(fila.id, destino, entorno.base.usuario)
    _assert_sin_ficha(entorno, session_factory)


@pytest.mark.parametrize(
    "vinculo", [EstadoTurno.ATENDIDO, EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO]
)
def test_otro_turno_permitido_o_atencion_previa_conservan_ficha(entorno, vinculo):
    asignar(entorno, vinculo)
    otro = asignar(entorno, EstadoTurno.CONFIRMADO, inicio=INICIO + timedelta(hours=1))
    with tenant_context(entorno.base.tenant.id, "demo"):
        transicionar(otro.id, EstadoTurno.CANCELADO, entorno.base.usuario)
    assert _visible(entorno).id == entorno.base.paciente.id


@pytest.mark.parametrize("estado", [EstadoTurno.RESERVADO, EstadoTurno.ATENDIDO])
def test_duplicados_y_reutilizacion_incluyen_el_mismo_vinculo(entorno, estado):
    asignar(entorno, estado)
    base = entorno.base
    with tenant_context(base.tenant.id, "demo"), tenant_session(base.tenant.id) as session:
        reutilizado = crear_o_reutilizar_paciente(
            session,
            nombre=base.paciente.nombre,
            telefono=base.paciente.telefono,
            usuario_id=entorno.usuario.id,
            alcance=AlcancePacientes.PROPIOS,
        )
        assert not reutilizado.creado and reutilizado.identidad.id == base.paciente.id
        creado = crear_paciente(
            session,
            PacienteCreate(nombre=base.paciente.nombre, telefono=base.paciente.telefono),
            entorno.usuario,
        )
        assert [p.id for p in creado.advertencia.duplicados] == [base.paciente.id]


@pytest.mark.parametrize("estado", [EstadoTurno.CANCELADO, EstadoTurno.AUSENTE])
def test_duplicados_y_reutilizacion_no_filtran_ficha_sin_vinculo(entorno, estado):
    asignar(entorno, estado)
    base = entorno.base
    with tenant_context(base.tenant.id, "demo"), tenant_session(base.tenant.id) as session:
        nuevo = crear_paciente(
            session,
            PacienteCreate(nombre=base.paciente.nombre, telefono=base.paciente.telefono),
            entorno.usuario,
        )
        assert nuevo.advertencia is None
        reutilizado = crear_o_reutilizar_paciente(
            session,
            nombre=base.paciente.nombre,
            telefono=base.paciente.telefono,
            usuario_id=entorno.usuario.id,
            alcance=AlcancePacientes.PROPIOS,
        )
        assert reutilizado.identidad.id == nuevo.paciente.id != base.paciente.id


@pytest.mark.parametrize("vinculado", [False, True])
def test_creador_conserva_su_ficha_sin_turnos_activos(entorno, session_factory, vinculado):
    with session_factory() as session:
        usuario = entorno.usuario
        if not vinculado:
            usuario = crear_usuario(
                session, entorno.base.tenant, "sinvinculo@demo", RolUsuario.PROFESIONAL
            )
        session.get(Paciente, entorno.base.paciente.id).creado_por_usuario_id = usuario.id
        session.commit()
    if vinculado:
        asignar(entorno, EstadoTurno.CANCELADO)
    assert _visible(entorno, usuario).id == entorno.base.paciente.id


def test_profesional_sin_vinculo_no_hereda_la_agenda_de_otro(entorno, session_factory):
    asignar(entorno, EstadoTurno.ATENDIDO)
    with session_factory() as session:
        otro = crear_usuario(
            session, entorno.base.tenant, "sinvinculo@demo", RolUsuario.PROFESIONAL
        )
    with pytest.raises(DomainError) as exc:
        _visible(entorno, otro)
    assert exc.value.code == "RN-AU-03"


def test_turnos_de_otro_profesional_no_otorgan_ficha(entorno, session_factory):
    with tenant_context(entorno.base.tenant.id, "demo"):
        crear(TurnoCreate(**entorno.base.datos()), entorno.base.usuario, ahora=AHORA)
    _assert_sin_ficha(entorno, session_factory)


def test_predicado_no_confia_en_una_referencia_uuid_de_otro_tenant(entorno, session_factory):
    with session_factory() as session:
        ajeno = entorno_turnos(session, "otro")
        # Fila adversarial de prueba: las FKs simples no codifican tenant compuesto.
        # El servicio jamás la crea; el predicado también debe aislarla.
        session.add(
            Turno(
                tenant_id=ajeno.tenant.id,
                profesional_id=entorno.profesional.id,
                paciente_id=entorno.base.paciente.id,
                prestacion_id=ajeno.prestacion.id,
                inicio=INICIO,
                fin=INICIO + timedelta(minutes=30),
                estado=EstadoTurno.ATENDIDO,
                codigo_publico="otrotenant01",
                es_sobreturno=False,
            )
        )
        session.commit()
    _assert_sin_ficha(entorno, session_factory)
