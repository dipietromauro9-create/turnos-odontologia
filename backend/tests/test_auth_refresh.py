"""Refresh: rotación con blacklist, reuso rechazado y aislamiento por tenant."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import crear_token, decodificar_token
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


def _login_y_refresh(app: FastAPI) -> tuple[TestClient, str, str]:
    client = cliente(app)
    respuesta = login(client)
    assert respuesta.status_code == 200
    refresh = respuesta.cookies.get("refresh_token")
    assert refresh
    return client, respuesta.json()["access_token"], refresh


def _refresh(app: FastAPI, token: str) -> object:
    return cliente(app).post("/auth/refresh", cookies={"refresh_token": token})


def test_un_refresh_valido_devuelve_un_par_nuevo(entorno: Entorno) -> None:
    _, access_viejo, refresh_viejo = _login_y_refresh(entorno.app)

    respuesta = _refresh(entorno.app, refresh_viejo)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["access_token"] != access_viejo
    assert cuerpo["expires_in"] == 15 * 60
    refresh_nuevo = respuesta.cookies.get("refresh_token")
    assert refresh_nuevo and refresh_nuevo != refresh_viejo


def test_el_par_nuevo_conserva_identidad_y_tenant(entorno: Entorno) -> None:
    _, _, refresh_viejo = _login_y_refresh(entorno.app)
    original = decodificar_token(refresh_viejo, tipo_esperado="refresh")

    respuesta = _refresh(entorno.app, refresh_viejo)

    access = decodificar_token(respuesta.json()["access_token"], tipo_esperado="access")
    refresh = decodificar_token(
        respuesta.cookies.get("refresh_token") or "", tipo_esperado="refresh"
    )
    for payload in (access, refresh):
        assert payload["sub"] == original["sub"] == str(entorno.consultorio.dueno.id)
        assert payload["tenant_id"] == original["tenant_id"] == str(entorno.consultorio.tenant.id)
        assert payload["email"] == EMAIL_DUENO


def test_reusar_el_refresh_rotado_responde_401(entorno: Entorno) -> None:
    _, _, refresh_viejo = _login_y_refresh(entorno.app)
    primera = _refresh(entorno.app, refresh_viejo)
    assert primera.status_code == 200

    segunda = _refresh(entorno.app, refresh_viejo)

    assert segunda.status_code == 401
    assert segunda.json()["code"] == "RN-AU-01"
    assert segunda.json()["details"]["reason"] == "refresh_revocado"
    assert segunda.cookies.get("refresh_token") is None
    assert "access_token" not in segunda.json()


def test_el_refresh_sin_cookie_responde_401(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).post("/auth/refresh")

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"
    assert respuesta.cookies.get("refresh_token") is None


def test_un_access_token_no_sirve_como_refresh(entorno: Entorno) -> None:
    _, access, _ = _login_y_refresh(entorno.app)

    respuesta = _refresh(entorno.app, access)

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_invalido"


def test_un_refresh_de_otro_tenant_se_rechaza(entorno: Entorno) -> None:
    token_ajeno = crear_token(
        sub=entorno.consultorio.dueno.id,
        tenant_id=uuid.uuid4(),
        email=EMAIL_DUENO,
        roles=["profesional"],
        tipo="refresh",
    )

    respuesta = _refresh(entorno.app, token_ajeno)

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_invalido"


def test_un_refresh_expirado_se_rechaza_de_forma_distinguible(entorno: Entorno) -> None:
    token_expirado = crear_token(
        sub=entorno.consultorio.dueno.id,
        tenant_id=entorno.consultorio.tenant.id,
        email=EMAIL_DUENO,
        roles=["profesional"],
        tipo="refresh",
        ahora=datetime.now(UTC) - timedelta(days=8),
    )

    respuesta = _refresh(entorno.app, token_expirado)

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_expirado"


def test_un_refresh_con_firma_invalida_se_rechaza(entorno: Entorno) -> None:
    _, _, refresh = _login_y_refresh(entorno.app)

    respuesta = _refresh(entorno.app, f"{refresh}manipulado")

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_invalido"
