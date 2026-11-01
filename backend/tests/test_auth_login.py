"""Login: Argon2id, par de tokens y respuestas indistinguibles ante fallos."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import decodificar_token
from app.core.token_store import InMemoryTokenStore
from app.db.models import Usuario
from tests.auth_helpers import (
    EMAIL_DUENO,
    Consultorio,
    app_de_prueba,
    cliente,
    crear_consultorio,
    login,
)

pytestmark = pytest.mark.integration

CLAIMS_REQUERIDOS = {"sub", "tenant_id", "roles", "email", "jti", "type", "iat", "exp"}


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


def test_login_correcto_emite_access_y_cookie_http_only(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    respuesta = login(client)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == 15 * 60
    cookies = respuesta.headers.get_list("set-cookie")
    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie.startswith("refresh_token=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie


def test_el_access_lleva_los_claims_y_su_vida(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    respuesta = login(client)

    payload = decodificar_token(respuesta.json()["access_token"], tipo_esperado="access")
    assert payload.keys() >= CLAIMS_REQUERIDOS
    assert payload["sub"] == str(entorno.consultorio.dueno.id)
    assert payload["tenant_id"] == str(entorno.consultorio.tenant.id)
    assert payload["email"] == EMAIL_DUENO
    assert payload["roles"] == ["profesional"]
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_la_cookie_de_refresh_lleva_los_claims_y_su_vida(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    respuesta = login(client)

    refresh = respuesta.cookies.get("refresh_token")
    assert refresh
    payload = decodificar_token(refresh, tipo_esperado="refresh")
    assert payload["sub"] == str(entorno.consultorio.dueno.id)
    assert payload["tenant_id"] == str(entorno.consultorio.tenant.id)
    assert payload["type"] == "refresh"
    assert payload["exp"] - payload["iat"] == 7 * 24 * 60 * 60


def test_password_incorrecta_no_emite_tokens(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    respuesta = login(client, password="clave-equivocada-2026")

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"
    assert respuesta.headers.get_list("set-cookie") == []


def test_email_inexistente_responde_igual_que_password_incorrecta(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    con_password_mala = login(client, password="clave-equivocada-2026")
    con_email_inexistente = login(client, email="nadie@demo", password="clave-equivocada-2026")

    assert con_email_inexistente.status_code == con_password_mala.status_code == 401
    assert con_email_inexistente.json() == con_password_mala.json()
    assert con_email_inexistente.headers.get_list("set-cookie") == []


def test_usuario_inactivo_no_puede_iniciar_sesion(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        usuario = session.get(Usuario, entorno.consultorio.dueno.id)
        assert usuario is not None
        usuario.activo = False
        session.commit()
    client = cliente(entorno.app)

    respuesta = login(client)

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"
    assert respuesta.headers.get_list("set-cookie") == []
    assert "access_token" not in respuesta.json()


def test_los_tiempos_de_vida_salen_de_la_configuracion(
    entorno: Entorno, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings

    monkeypatch.setenv("ACCESS_MINUTES", "5")
    get_settings.cache_clear()
    client = cliente(entorno.app)

    respuesta = login(client)

    acceso = decodificar_token(respuesta.json()["access_token"], tipo_esperado="access")
    refresh = decodificar_token(
        respuesta.cookies.get("refresh_token") or "", tipo_esperado="refresh"
    )
    assert acceso["exp"] - acceso["iat"] == 5 * 60
    assert respuesta.json()["expires_in"] == 5 * 60
    assert refresh["exp"] - refresh["iat"] == 7 * 24 * 60 * 60
