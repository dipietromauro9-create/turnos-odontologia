"""Lectura, edición parcial y alcance RN-AU-03 sobre pacientes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import Paciente, RolUsuario, Tenant, Usuario
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.dependencies import alcance_pacientes
from app.domain.pacientes.schemas import PacienteUpdate
from app.domain.pacientes.service import (
    actualizar_paciente,
    buscar_pacientes,
    obtener_paciente,
)
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    tenant: Tenant
    dueno: Usuario
    recepcion: Usuario
    profesional: Usuario


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        tenant = crear_tenant(session)
        dueno = crear_usuario(
            session, tenant, "dueno@demo", rol=RolUsuario.PROFESIONAL, es_dueno=True
        )
        recepcion = crear_usuario(session, tenant, "recepcion@demo")
        profesional = crear_usuario(session, tenant, "profesional@demo", rol=RolUsuario.PROFESIONAL)
    return Entorno(tenant=tenant, dueno=dueno, recepcion=recepcion, profesional=profesional)


def _crear_paciente(
    entorno: Entorno,
    session_factory: sessionmaker[Session],
    *,
    creador: Usuario,
    nombre: str = "Paciente Ficticio",
    telefono: str = "1145550001",
    observaciones: str | None = "Observación inicial",
) -> uuid.UUID:
    with tenant_session(entorno.tenant.id) as session:
        paciente = Paciente(
            tenant_id=entorno.tenant.id,
            nombre=nombre,
            telefono=telefono,
            observaciones=observaciones,
            creado_por_usuario_id=creador.id,
        )
        session.add(paciente)
        session.commit()
        return paciente.id


def _obtener(entorno: Entorno, paciente_id: uuid.UUID, usuario: Usuario) -> Paciente:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        return obtener_paciente(session, paciente_id, usuario)


def _actualizar(
    entorno: Entorno, paciente_id: uuid.UUID, usuario: Usuario, datos: PacienteUpdate
) -> Paciente:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        paciente = actualizar_paciente(session, paciente_id, datos, usuario)
        session.commit()
        return paciente


def _listar(entorno: Entorno, usuario: Usuario) -> list[Paciente]:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        return buscar_pacientes(
            session,
            alcance=alcance_pacientes(usuario),
            usuario_id=usuario.id,
        )


@pytest.mark.parametrize("actor", ["recepcion", "dueno"])
def test_recepcion_y_dueno_leen_y_editan_cualquier_paciente(
    entorno: Entorno, session_factory: sessionmaker[Session], actor: str
) -> None:
    usuario = getattr(entorno, actor)
    paciente_id = _crear_paciente(entorno, session_factory, creador=entorno.profesional)

    leido = _obtener(entorno, paciente_id, usuario)
    editado = _actualizar(entorno, paciente_id, usuario, PacienteUpdate(observaciones="Editado"))

    assert leido.id == paciente_id
    assert editado.observaciones == "Editado"


def test_el_profesional_sin_flag_lista_solo_los_suyos(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    propio = _crear_paciente(
        entorno, session_factory, creador=entorno.profesional, nombre="Propio Ficticio"
    )
    _crear_paciente(entorno, session_factory, creador=entorno.recepcion, nombre="Ajeno Ficticio")

    listado = _listar(entorno, entorno.profesional)

    assert [paciente.id for paciente in listado] == [propio]


@pytest.mark.parametrize("accion", ["leer", "editar"])
def test_el_profesional_sin_flag_no_toca_un_paciente_ajeno(
    entorno: Entorno, session_factory: sessionmaker[Session], accion: str
) -> None:
    ajeno = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    with pytest.raises(DomainError) as exc:
        if accion == "leer":
            _obtener(entorno, ajeno, entorno.profesional)
        else:
            _actualizar(
                entorno, ajeno, entorno.profesional, PacienteUpdate(observaciones="Hackeado")
            )

    assert exc.value.status_code == 403
    assert exc.value.code == "RN-AU-03"
    assert exc.value.details == {"reason": "fuera_de_alcance"}

    with tenant_session(entorno.tenant.id) as session:
        sigue = session.get(Paciente, ajeno)
    assert sigue is not None
    assert sigue.observaciones == "Observación inicial"


def test_un_patch_parcial_cambia_solo_los_campos_enviados(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente_id = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    editado = _actualizar(
        entorno,
        paciente_id,
        entorno.recepcion,
        PacienteUpdate(observaciones="Solo observaciones"),
    )

    assert editado.observaciones == "Solo observaciones"
    assert editado.nombre == "Paciente Ficticio"
    assert editado.telefono == "1145550001"


def test_un_paciente_creado_por_el_profesional_aparece_en_su_listado(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    from app.db.session import tenant_context as contexto
    from app.domain.pacientes.schemas import PacienteCreate
    from app.domain.pacientes.service import crear_paciente

    with (
        contexto(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        resultado = crear_paciente(
            session,
            PacienteCreate(nombre="Propio Ficticio", telefono="1145550009"),
            entorno.profesional,
        )
        session.commit()
        creado_id = resultado.paciente.id

    listado = _listar(entorno, entorno.profesional)

    assert [paciente.id for paciente in listado] == [creado_id]


def test_un_id_inexistente_responde_404_rn_pa_02(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with pytest.raises(DomainError) as exc:
        _obtener(entorno, uuid.uuid4(), entorno.recepcion)

    assert exc.value.status_code == 404
    assert exc.value.code == "RN-PA-02"
    assert exc.value.details == {"reason": "no_encontrado"}


def test_un_paciente_de_otro_tenant_responde_404_y_no_403(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = Paciente(tenant_id=otro.id, nombre="Ajeno Ficticio", telefono="1145550077")
        session.add(ajeno)
        session.commit()
        ajeno_id = ajeno.id

    with pytest.raises(DomainError) as exc:
        _obtener(entorno, ajeno_id, entorno.profesional)

    assert exc.value.status_code == 404
    assert exc.value.code == "RN-PA-02"


def test_un_patch_vacio_devuelve_el_paciente_sin_cambios(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente_id = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    editado = _actualizar(entorno, paciente_id, entorno.recepcion, PacienteUpdate())

    assert editado.id == paciente_id
    assert editado.nombre == "Paciente Ficticio"
    assert editado.telefono == "1145550001"
    assert editado.observaciones == "Observación inicial"


def test_el_rol_enviado_en_el_body_es_rechazado(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    from pydantic import ValidationError

    paciente_id = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    with pytest.raises(ValidationError):
        PacienteUpdate.model_validate({"rol": "profesional"})

    with tenant_session(entorno.tenant.id) as session:
        sin_cambios = session.get(Paciente, paciente_id)
    assert sin_cambios is not None
    assert sin_cambios.tenant_id == entorno.tenant.id


@pytest.mark.parametrize("campo", ["nombre", "telefono"])
def test_un_campo_no_nulo_enviado_como_nulo_responde_422(
    entorno: Entorno, session_factory: sessionmaker[Session], campo: str
) -> None:
    paciente_id = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    with pytest.raises(DomainError) as exc:
        _actualizar(entorno, paciente_id, entorno.recepcion, PacienteUpdate(**{campo: None}))

    assert exc.value.status_code == 422
    assert exc.value.details == {"reason": "campo_invalido", "campo": campo}
