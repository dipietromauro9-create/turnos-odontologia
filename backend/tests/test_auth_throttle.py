"""Bloqueo por cuenta y límite de tasa por IP+email, con reloj inyectado."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.token_store import MAX_FALLOS, InMemoryTokenStore
from tests.auth_helpers import (
    EMAIL_DUENO,
    EMAIL_RECEPCION,
    Consultorio,
    app_de_prueba,
    cliente,
    crear_consultorio,
    login,
)

pytestmark = pytest.mark.integration

SEGUNDOS_ENTRE_INTENTOS = 61


class RelojFalso:
    def __init__(self) -> None:
        self.ahora = 1_000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


@dataclass(frozen=True)
class Entorno:
    app: FastAPI
    store: InMemoryTokenStore
    consultorio: Consultorio


@pytest.fixture()
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session], reloj: RelojFalso) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session, con_recepcion=True)
    app, store = app_de_prueba(InMemoryTokenStore(reloj=reloj))
    assert isinstance(store, InMemoryTokenStore)
    return Entorno(app=app, store=store, consultorio=consultorio)


def _fallar(client: object, reloj: RelojFalso, *, email: str = EMAIL_DUENO) -> object:
    respuesta = client.post(  # type: ignore[attr-defined]
        "/auth/login", json={"email": email, "password": "clave-equivocada-2026"}
    )
    assert respuesta.status_code == 401
    reloj.avanzar(SEGUNDOS_ENTRE_INTENTOS)
    return respuesta


def test_diez_fallos_bloquean_incluso_con_la_password_correcta(
    entorno: Entorno, reloj: RelojFalso
) -> None:
    client = cliente(entorno.app)
    for _ in range(MAX_FALLOS):
        _fallar(client, reloj)

    respuesta = login(client)

    assert respuesta.status_code == 429
    assert respuesta.json()["code"] == "RN-AU-01"
    assert respuesta.json()["details"]["reason"] == "cuenta_bloqueada"
    assert int(respuesta.headers["Retry-After"]) > 0
    assert respuesta.headers.get_list("set-cookie") == []
    assert "access_token" not in respuesta.json()
    assert entorno.store.esta_bloqueado(
        entorno.consultorio.tenant.id, entorno.consultorio.dueno.id
    ).bloqueado


def test_el_bloqueo_expira_y_la_cuenta_vuelve_a_entrar(entorno: Entorno, reloj: RelojFalso) -> None:
    client = cliente(entorno.app)
    for _ in range(MAX_FALLOS):
        _fallar(client, reloj)
    assert login(client).status_code == 429

    reloj.avanzar(15 * 60 + 1)

    respuesta = login(client)
    assert respuesta.status_code == 200
    assert "access_token" in respuesta.json()


def test_un_login_exitoso_reinicia_el_contador(entorno: Entorno, reloj: RelojFalso) -> None:
    client = cliente(entorno.app)
    tenant_id = entorno.consultorio.tenant.id
    usuario_id = entorno.consultorio.dueno.id

    for _ in range(MAX_FALLOS - 1):
        _fallar(client, reloj)
    assert login(client).status_code == 200
    assert entorno.store.esta_bloqueado(tenant_id, usuario_id).bloqueado is False

    for _ in range(MAX_FALLOS - 1):
        _fallar(client, reloj)
    assert entorno.store.esta_bloqueado(tenant_id, usuario_id).bloqueado is False

    _fallar(client, reloj)
    assert entorno.store.esta_bloqueado(tenant_id, usuario_id).bloqueado is True


def test_el_sexto_intento_en_un_minuto_se_rechaza_por_tasa(entorno: Entorno) -> None:
    client = cliente(entorno.app)
    for _ in range(5):
        assert login(client, password="clave-equivocada-2026").status_code == 401

    respuesta = login(client)

    assert respuesta.status_code == 429
    assert respuesta.json()["details"]["reason"] == "rate_limit"
    assert int(respuesta.headers["Retry-After"]) > 0
    assert respuesta.headers.get_list("set-cookie") == []


def test_otro_email_no_hereda_la_cuota_agotada(entorno: Entorno) -> None:
    client = cliente(entorno.app)
    for _ in range(5):
        assert login(client, password="clave-equivocada-2026").status_code == 401
    assert login(client).status_code == 429

    respuesta = login(client, email=EMAIL_RECEPCION)

    assert respuesta.status_code == 200
    assert "access_token" in respuesta.json()


def test_los_logins_exitosos_tambien_consumen_cuota(entorno: Entorno) -> None:
    client = cliente(entorno.app)
    for _ in range(5):
        assert login(client).status_code == 200

    respuesta = login(client)

    assert respuesta.status_code == 429
    assert respuesta.json()["details"]["reason"] == "rate_limit"
