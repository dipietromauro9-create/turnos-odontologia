"""Borrado físico v1 sin auditoría ni soft delete (RN-PA-03, DD-07, IN-01)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import Paciente, Tenant, Usuario
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.dependencies import alcance_pacientes
from app.domain.pacientes.service import (
    buscar_pacientes,
    eliminar_paciente,
    obtener_paciente,
)
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration

PROHIBIDAS = ("deleted_at", "eliminado_en", "activo")


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


def _crear(
    entorno: Entorno,
    session_factory: sessionmaker[Session],
    *,
    nombre: str = "Paciente Ficticio",
    telefono: str = "1145550001",
) -> uuid.UUID:
    with tenant_session(entorno.tenant.id) as session:
        paciente = Paciente(
            tenant_id=entorno.tenant.id,
            nombre=nombre,
            telefono=telefono,
            creado_por_usuario_id=entorno.recepcion.id,
        )
        session.add(paciente)
        session.commit()
        return paciente.id


def _eliminar(entorno: Entorno, paciente_id: uuid.UUID) -> bool:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        eliminado = eliminar_paciente(session, paciente_id, entorno.recepcion)
        session.commit()
        return eliminado


def test_la_tabla_no_tiene_columnas_de_borrado_logico(db_engine: object) -> None:
    columnas = {
        columna["name"]
        for columna in inspect(db_engine).get_columns("paciente")  # type: ignore[arg-type]
    }

    assert columnas.isdisjoint(PROHIBIDAS)


def test_el_borrado_elimina_la_fila_fisicamente(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente_id = _crear(entorno, session_factory)

    assert _eliminar(entorno, paciente_id) is True

    with session_factory() as session:
        assert session.get(Paciente, paciente_id) is None
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
        pytest.raises(DomainError) as exc,
    ):
        obtener_paciente(session, paciente_id, entorno.recepcion)
    assert exc.value.code == "RN-PA-02"


def test_un_segundo_borrado_devuelve_false(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente_id = _crear(entorno, session_factory)

    assert _eliminar(entorno, paciente_id) is True
    assert _eliminar(entorno, paciente_id) is False


def test_borrar_un_id_de_otro_tenant_no_elimina_nada(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = Paciente(tenant_id=otro.id, nombre="Ajeno Ficticio", telefono="1145550077")
        session.add(ajeno)
        session.commit()
        ajeno_id = ajeno.id

    assert _eliminar(entorno, ajeno_id) is False

    with session_factory() as session:
        assert session.get(Paciente, ajeno_id) is not None


def test_tras_el_borrado_desaparece_del_listado_y_de_la_busqueda(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    paciente_id = _crear(entorno, session_factory, nombre="María González")
    _eliminar(entorno, paciente_id)

    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        listado = buscar_pacientes(
            session,
            alcance=alcance_pacientes(entorno.recepcion),
            usuario_id=entorno.recepcion.id,
        )
        buscado = buscar_pacientes(
            session,
            q="maria gonzales",
            alcance=alcance_pacientes(entorno.recepcion),
            usuario_id=entorno.recepcion.id,
        )
    assert listado == []
    assert buscado == []


def test_no_existe_tabla_de_auditoria(db_engine: object) -> None:
    tablas = {
        nombre.lower()
        for nombre in inspect(db_engine).get_table_names()  # type: ignore[arg-type]
    }

    assert not any("audit" in nombre or "auditor" in nombre for nombre in tablas)


def test_un_profesional_sin_flag_no_borra_un_paciente_ajeno(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    from app.db.models import RolUsuario

    with session_factory() as session:
        profesional = crear_usuario(
            session, entorno.tenant, "profesional@demo", rol=RolUsuario.PROFESIONAL
        )
    paciente_id = _crear(entorno, session_factory)

    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        with pytest.raises(DomainError) as exc:
            eliminar_paciente(session, paciente_id, profesional)
        session.rollback()

    assert exc.value.code == "RN-AU-03"
    with session_factory() as session:
        assert session.get(Paciente, paciente_id) is not None


def test_no_hay_ruta_http_de_borrado(app_env: None) -> None:
    from fastapi.routing import APIRoute

    from tests.auth_helpers import app_de_prueba

    app, _ = app_de_prueba()
    borrados = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/pacientes")
        and "DELETE" in route.methods
    ]

    assert borrados == []
