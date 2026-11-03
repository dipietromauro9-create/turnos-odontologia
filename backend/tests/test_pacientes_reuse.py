"""Contrato de reutilización por teléfono para C-09 (RN-PA-01, RN-PA-02)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Paciente, RolUsuario, Tenant, Usuario
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.dependencies import AlcancePacientes
from app.domain.pacientes.service import crear_o_reutilizar_paciente
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    tenant: Tenant
    recepcion: Usuario


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        tenant = crear_tenant(session)
        recepcion = crear_usuario(session, tenant, "recepcion@demo")
    return Entorno(tenant=tenant, recepcion=recepcion)


def _reutilizar(
    entorno: Entorno,
    *,
    nombre: str,
    telefono: str,
    usuario_id: uuid.UUID | None,
    alcance: AlcancePacientes = AlcancePacientes.TODOS,
) -> object:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        resultado = crear_o_reutilizar_paciente(
            session,
            nombre=nombre,
            telefono=telefono,
            usuario_id=usuario_id,
            alcance=alcance,
        )
        session.commit()
        return resultado


def _crear_paciente(
    entorno: Entorno,
    session_factory: sessionmaker[Session],
    *,
    nombre: str = "María González",
    telefono: str = "1145550001",
    creador: Usuario | None = None,
) -> Paciente:
    with tenant_session(entorno.tenant.id) as session:
        paciente = Paciente(
            tenant_id=entorno.tenant.id,
            nombre=nombre,
            telefono=telefono,
            observaciones="No debe viajar al turnero",
            creado_por_usuario_id=creador.id if creador else None,
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        return paciente


def test_un_telefono_existente_reutiliza_al_paciente(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    existente = _crear_paciente(entorno, session_factory)

    resultado = _reutilizar(
        entorno,
        nombre="María G.",
        telefono="11 4555-0001",
        usuario_id=entorno.recepcion.id,
    )

    assert resultado.creado is False
    assert resultado.identidad.id == existente.id
    assert resultado.advertencia is None


def test_un_telefono_nuevo_crea_el_paciente(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    resultado = _reutilizar(
        entorno,
        nombre="Paciente Nuevo",
        telefono="1145550009",
        usuario_id=entorno.recepcion.id,
    )

    assert resultado.creado is True
    with session_factory() as session:
        persistido = session.get(Paciente, resultado.identidad.id)
    assert persistido is not None
    assert persistido.tenant_id == entorno.tenant.id
    assert persistido.creado_por_usuario_id == entorno.recepcion.id


def test_el_resultado_expone_solo_la_identidad_minima(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _crear_paciente(entorno, session_factory)

    resultado = _reutilizar(
        entorno,
        nombre="María González",
        telefono="1145550001",
        usuario_id=entorno.recepcion.id,
    )

    assert set(resultado.identidad.model_dump()) == {"id", "nombre", "telefono"}
    assert not hasattr(resultado, "paciente")
    assert "observaciones" not in resultado.identidad.model_dump()


def test_un_telefono_de_otro_tenant_crea_uno_nuevo(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        session.add(Paciente(tenant_id=otro.id, nombre="Ajeno Ficticio", telefono="1145550001"))
        session.commit()

    resultado = _reutilizar(
        entorno,
        nombre="María González",
        telefono="1145550001",
        usuario_id=entorno.recepcion.id,
    )

    assert resultado.creado is True
    with session_factory() as session:
        creado = session.get(Paciente, resultado.identidad.id)
    assert creado is not None
    assert creado.tenant_id == entorno.tenant.id


def test_sin_usuario_el_paciente_creado_queda_sin_creador(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    resultado = _reutilizar(
        entorno,
        nombre="Reserva Pública Ficticia",
        telefono="1145550010",
        usuario_id=None,
    )

    with session_factory() as session:
        creado = session.get(Paciente, resultado.identidad.id)
    assert creado is not None
    assert creado.creado_por_usuario_id is None


def test_mismo_nombre_con_otro_telefono_crea_y_advierte(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    existente = _crear_paciente(entorno, session_factory)

    resultado = _reutilizar(
        entorno,
        nombre="  María González ",
        telefono="1145550022",
        usuario_id=entorno.recepcion.id,
    )

    assert resultado.creado is True
    assert resultado.identidad.id != existente.id
    assert resultado.advertencia is not None
    assert resultado.advertencia.codigo == "RN-PA-01"
    assert [d.id for d in resultado.advertencia.duplicados or []] == [existente.id]


def test_sin_usuario_la_advertencia_no_expone_duplicados(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _crear_paciente(entorno, session_factory)

    resultado = _reutilizar(
        entorno,
        nombre="María González",
        telefono="1145550023",
        usuario_id=None,
    )

    assert resultado.creado is True
    assert resultado.advertencia is not None
    assert resultado.advertencia.duplicados is None


def test_un_profesional_sin_flag_no_reutiliza_un_paciente_ajeno(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        profesional = crear_usuario(
            session, entorno.tenant, "profesional@demo", rol=RolUsuario.PROFESIONAL
        )
    ajeno = _crear_paciente(entorno, session_factory, creador=entorno.recepcion)

    resultado = _reutilizar(
        entorno,
        nombre="María González",
        telefono=ajeno.telefono,
        usuario_id=profesional.id,
        alcance=AlcancePacientes.PROPIOS,
    )

    assert resultado.creado is True
    assert resultado.identidad.id != ajeno.id


def test_la_reutilizacion_no_duplica_al_reejecutarse(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    primero = _reutilizar(
        entorno,
        nombre="Paciente Idempotente",
        telefono="1145550033",
        usuario_id=entorno.recepcion.id,
    )
    segundo = _reutilizar(
        entorno,
        nombre="Paciente Idempotente",
        telefono="11 4555 0033",
        usuario_id=entorno.recepcion.id,
    )

    assert segundo.creado is False
    assert segundo.identidad.id == primero.identidad.id
    with session_factory() as session:
        filas = (
            session.execute(select(Paciente).where(Paciente.telefono == "1145550033"))
            .scalars()
            .all()
        )
    assert len(filas) == 1
