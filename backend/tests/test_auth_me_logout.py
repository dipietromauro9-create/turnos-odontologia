"""Identidad actual (/auth/me) y cierre de sesión idempotente (/auth/logout)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import crear_token
from app.core.token_store import InMemoryTokenStore
from app.db.models import RolUsuario
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

CAMPOS_ME = {"id", "tenant_id", "nombre", "email", "rol", "es_dueno"}


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


def _login(app: FastAPI) -> tuple[str, str]:
    respuesta = login(cliente(app))
    assert respuesta.status_code == 200
    refresh = respuesta.cookies.get("refresh_token")
    assert refresh
    return respuesta.json()["access_token"], refresh


def test_me_devuelve_el_usuario_del_token(entorno: Entorno) -> None:
    access, _ = _login(entorno.app)

    respuesta = cliente(entorno.app).get("/auth/me", headers={"Authorization": f"Bearer {access}"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_ME
    assert cuerpo["id"] == str(entorno.consultorio.dueno.id)
    assert cuerpo["tenant_id"] == str(entorno.consultorio.tenant.id)
    assert cuerpo["nombre"] == "Persona Ficticia"
    assert cuerpo["email"] == EMAIL_DUENO
    assert cuerpo["rol"] == "profesional"
    assert cuerpo["es_dueno"] is True


def test_me_nunca_expone_el_hash_de_la_password(entorno: Entorno) -> None:
    access, _ = _login(entorno.app)

    respuesta = cliente(entorno.app).get("/auth/me", headers={"Authorization": f"Bearer {access}"})

    assert respuesta.status_code == 200
    assert "password_hash" not in respuesta.text
    assert "argon2" not in respuesta.text
    assert "password" not in respuesta.json()


def test_me_no_consulta_datos_de_otro_tenant(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = crear_usuario_con_password(
            session, otro, "ajeno@otro", "clave-ajena-2026", rol=RolUsuario.PROFESIONAL
        )
    token_ajeno = crear_token(
        sub=ajeno.id,
        tenant_id=otro.id,
        email=ajeno.email,
        roles=["profesional"],
        tipo="access",
    )

    respuesta = cliente(entorno.app).get(
        "/auth/me", headers={"Authorization": f"Bearer {token_ajeno}"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


def test_logout_invalida_el_refresh_y_borra_la_cookie(entorno: Entorno) -> None:
    _, refresh = _login(entorno.app)
    client = cliente(entorno.app)

    logout = client.post("/auth/logout", cookies={"refresh_token": refresh})

    assert logout.status_code == 204
    cookie = logout.headers.get_list("set-cookie")[0]
    assert cookie.startswith("refresh_token=")
    assert "Max-Age=0" in cookie

    posterior = cliente(entorno.app).post("/auth/refresh", cookies={"refresh_token": refresh})
    assert posterior.status_code == 401


def test_logout_repetido_o_sin_cookie_es_exitoso(entorno: Entorno) -> None:
    _, refresh = _login(entorno.app)
    client = cliente(entorno.app)

    primero = client.post("/auth/logout", cookies={"refresh_token": refresh})
    segundo = client.post("/auth/logout", cookies={"refresh_token": refresh})
    sin_cookie = client.post("/auth/logout")

    assert [primero.status_code, segundo.status_code, sin_cookie.status_code] == [204, 204, 204]
    for respuesta in (primero, segundo, sin_cookie):
        assert "refresh_token=" in respuesta.headers.get_list("set-cookie")[0]
