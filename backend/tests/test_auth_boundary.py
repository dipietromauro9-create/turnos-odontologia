"""Frontera HTTP: 401 del panel, rutas públicas y atributos de la cookie."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import crear_token
from app.core.token_store import InMemoryTokenStore
from tests.auth_helpers import (
    EMAIL_DUENO,
    Consultorio,
    app_de_prueba,
    cliente,
    crear_consultorio,
    login,
)

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


def _access_expirado(entorno: Entorno) -> str:
    return crear_token(
        sub=entorno.consultorio.dueno.id,
        tenant_id=entorno.consultorio.tenant.id,
        email=EMAIL_DUENO,
        roles=["profesional"],
        tipo="access",
        ahora=datetime.now(UTC) - timedelta(days=1),
    )


def test_me_sin_token_responde_401_con_el_sobre(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get("/auth/me")

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "RN-AU-01"
    assert cuerpo["message"]
    assert "password_hash" not in respuesta.text


def test_un_access_expirado_es_distinguible(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get(
        "/auth/me", headers={"Authorization": f"Bearer {_access_expirado(entorno)}"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"
    assert respuesta.json()["details"]["reason"] == "token_expirado"


def test_un_refresh_en_authorization_no_autentica(entorno: Entorno) -> None:
    refresh = login(cliente(entorno.app)).cookies.get("refresh_token")
    assert refresh

    respuesta = cliente(entorno.app).get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_invalido"


def test_health_sigue_publico(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_una_ruta_del_turnero_no_responde_401_por_falta_de_jwt(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get("/turnero/ping")

    assert respuesta.status_code != 401


def test_la_cookie_de_refresh_lleva_path_y_max_age(entorno: Entorno) -> None:
    respuesta = login(cliente(entorno.app))

    cookie = respuesta.headers.get_list("set-cookie")[0]
    assert "Path=/auth" in cookie
    assert "Max-Age=604800" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_la_cookie_usa_secure_solo_con_origen_https(
    entorno: Entorno, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings

    sin_https = login(cliente(entorno.app)).headers.get_list("set-cookie")[0]
    assert "Secure" not in sin_https

    monkeypatch.setenv("FRONTEND_ORIGIN", "https://panel.example")
    get_settings.cache_clear()
    con_https = login(cliente(entorno.app)).headers.get_list("set-cookie")[0]
    assert "Secure" in con_https
