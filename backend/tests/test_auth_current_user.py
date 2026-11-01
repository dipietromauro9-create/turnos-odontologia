"""`get_current_user`: la fila del tenant es la autoridad, no los claims."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import crear_token
from app.core.token_store import InMemoryTokenStore
from app.db.models import RolUsuario, Usuario
from tests.auth_helpers import (
    EMAIL_DUENO,
    Consultorio,
    app_de_prueba,
    cliente,
    crear_consultorio,
    login,
)
from tests.factories import crear_tenant, crear_usuario_con_password

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    app: FastAPI
    store: InMemoryTokenStore
    consultorio: Consultorio


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session)
    app, store = app_de_prueba()
    assert isinstance(store, InMemoryTokenStore)
    return Entorno(app=app, store=store, consultorio=consultorio)


def _me(entorno: Entorno, token: str) -> object:
    return cliente(entorno.app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def _access(entorno: Entorno, *, sub: uuid.UUID, tenant_id: uuid.UUID) -> str:
    return crear_token(
        sub=sub,
        tenant_id=tenant_id,
        email=EMAIL_DUENO,
        roles=["profesional"],
        tipo="access",
    )


def test_un_usuario_desactivado_pierde_el_acceso(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        usuario = session.get(Usuario, entorno.consultorio.dueno.id)
        assert usuario is not None
        usuario.activo = False
        session.commit()
    token = _access(
        entorno,
        sub=entorno.consultorio.dueno.id,
        tenant_id=entorno.consultorio.tenant.id,
    )

    respuesta = _me(entorno, token)

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "usuario_inactivo"


def test_un_token_de_otro_tenant_se_rechaza(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
    token = _access(entorno, sub=entorno.consultorio.dueno.id, tenant_id=otro.id)

    respuesta = _me(entorno, token)

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


def test_un_sub_de_otro_tenant_no_devuelve_datos_ajenos(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = crear_usuario_con_password(
            session, otro, "ajeno@otro", "clave-ajena-2026", rol=RolUsuario.PROFESIONAL
        )
    token = _access(entorno, sub=ajeno.id, tenant_id=entorno.consultorio.tenant.id)

    respuesta = _me(entorno, token)

    assert respuesta.status_code == 401
    assert "ajeno@otro" not in respuesta.text


def test_un_sub_inexistente_no_autentica(entorno: Entorno) -> None:
    token = _access(
        entorno,
        sub=uuid.uuid4(),
        tenant_id=entorno.consultorio.tenant.id,
    )

    respuesta = _me(entorno, token)

    assert respuesta.status_code == 401


def test_un_token_valido_del_usuario_activo_sigue_entrando(entorno: Entorno) -> None:
    access = login(cliente(entorno.app)).json()["access_token"]

    respuesta = _me(entorno, access)

    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == EMAIL_DUENO
