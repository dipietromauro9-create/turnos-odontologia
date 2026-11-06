"""Utilidades compartidas por los tests de auth (R9: solo datos ficticios)."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.token_store import InMemoryTokenStore, TokenStore
from app.db.models import RolUsuario, Tenant, Usuario
from app.domain.auth.dependencies import get_token_store
from tests.factories import crear_tenant, crear_usuario_con_password

PASSWORD = "clave-ficticia-2026"
EMAIL_DUENO = "dueno@demo"
EMAIL_RECEPCION = "recepcion@demo"


@dataclass(frozen=True)
class Consultorio:
    """Tenant demo con dueño (profesional) y, opcionalmente, recepción."""

    tenant: Tenant
    dueno: Usuario
    recepcion: Usuario | None = field(default=None)


def crear_consultorio(session: Session, *, con_recepcion: bool = False) -> Consultorio:
    tenant = crear_tenant(session)
    dueno = crear_usuario_con_password(
        session,
        tenant,
        EMAIL_DUENO,
        PASSWORD,
        rol=RolUsuario.PROFESIONAL,
        es_dueno=True,
    )
    recepcion = None
    if con_recepcion:
        recepcion = crear_usuario_con_password(session, tenant, EMAIL_RECEPCION, PASSWORD)
    return Consultorio(tenant=tenant, dueno=dueno, recepcion=recepcion)


def app_de_prueba(
    store: TokenStore | None = None,
    rate_limiter: object | None = None,
) -> tuple[FastAPI, TokenStore]:
    """App real con `TokenStore` y rate limiter en memoria (sin Redis en tests)."""
    from app.domain.turnero.rate_limit import InMemoryRateLimiter, get_rate_limiter
    from app.main import create_app

    store = store or InMemoryTokenStore()
    limiter = rate_limiter or InMemoryRateLimiter()
    app = create_app()
    app.dependency_overrides[get_token_store] = lambda: store
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    return app, store


def cliente(app: FastAPI) -> TestClient:
    return TestClient(app)


def login(
    client: TestClient,
    *,
    email: str = EMAIL_DUENO,
    password: str = PASSWORD,
) -> object:
    return client.post("/auth/login", json={"email": email, "password": password})


def autorizacion(app: FastAPI, email: str = EMAIL_DUENO) -> dict[str, str]:
    """Cabecera Authorization con un access real emitido por /auth/login."""
    respuesta = login(cliente(app), email=email)
    assert respuesta.status_code == 200
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}
