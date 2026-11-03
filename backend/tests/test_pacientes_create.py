"""Alta de paciente: persistencia tenant-scoped y advertencia de duplicado RN-PA-01."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Paciente, RolUsuario, Tenant, Usuario
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.schemas import PacienteCreate
from app.domain.pacientes.service import crear_paciente
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


def _alta(
    entorno: Entorno,
    *,
    usuario: Usuario,
    nombre: str,
    telefono: str,
) -> tuple[Paciente, object]:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        resultado = crear_paciente(
            session,
            PacienteCreate(nombre=nombre, telefono=telefono),
            usuario,
        )
        session.commit()
        return resultado.paciente, resultado.advertencia


def test_alta_sin_coincidencias_persiste_sin_advertencia(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente, advertencia = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia",
        telefono="11 4555-0001",
    )

    assert advertencia is None
    assert paciente.tenant_id == entorno.tenant.id
    assert paciente.creado_por_usuario_id == entorno.recepcion.id
    assert paciente.telefono == "1145550001"

    with session_factory() as session:
        persistido = session.get(Paciente, paciente.id)
    assert persistido is not None
    assert persistido.nombre == "Ana Ficticia"
    assert persistido.tenant_id == entorno.tenant.id


def test_mismo_telefono_normalizado_advierte_y_persiste_el_nuevo(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    primero, _ = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    segundo, advertencia = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia Dos",
        telefono="11 4555-0001",
    )

    assert advertencia is not None
    assert advertencia.codigo == "RN-PA-01"
    assert [duplicado.id for duplicado in advertencia.duplicados] == [primero.id]

    with session_factory() as session:
        assert session.get(Paciente, segundo.id) is not None
        assert session.query(Paciente).count() == 2


def test_mismo_nombre_normalizado_con_otro_telefono_tambien_advierte(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    primero, _ = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    _, advertencia = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="  Ana Ficticia ",
        telefono="1145559999",
    )

    assert advertencia is not None
    assert advertencia.codigo == "RN-PA-01"
    assert [duplicado.id for duplicado in advertencia.duplicados] == [primero.id]


def test_un_duplicado_de_otro_tenant_no_advierte(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        session.add(
            Paciente(
                tenant_id=otro.id,
                nombre="Ana Ficticia",
                telefono="1145550001",
            )
        )
        session.commit()

    _, advertencia = _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    assert advertencia is None


def test_la_advertencia_de_un_profesional_sin_flag_no_incluye_pacientes_ajenos(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _alta(
        entorno,
        usuario=entorno.recepcion,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    _, advertencia = _alta(
        entorno,
        usuario=entorno.profesional,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    assert advertencia is None


def test_un_profesional_sin_flag_si_advierte_su_propio_duplicado(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    primero, _ = _alta(
        entorno,
        usuario=entorno.profesional,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    _, advertencia = _alta(
        entorno,
        usuario=entorno.profesional,
        nombre="Ana Ficticia",
        telefono="1145550001",
    )

    assert advertencia is not None
    assert [duplicado.id for duplicado in advertencia.duplicados] == [primero.id]
