"""Middleware de borde: default-deny, allowlist pública y orden con el tenant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter, FastAPI
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


def _app_con_rutas_de_panel(store: InMemoryTokenStore | None = None) -> tuple[FastAPI, object]:
    app, store_real = app_de_prueba(store)
    extra = APIRouter()

    @extra.get("/panel/demo")
    def panel_demo() -> dict[str, bool]:
        return {"ok": True}

    @extra.get("/turnero/ping")
    def turnero_ping() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(extra)
    return app, store_real


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session)
    app, store = _app_con_rutas_de_panel()
    assert isinstance(store, InMemoryTokenStore)
    return Entorno(app=app, store=store, consultorio=consultorio)


def _access(entorno: Entorno, *, ahora: datetime | None = None) -> str:
    return crear_token(
        sub=entorno.consultorio.dueno.id,
        tenant_id=entorno.consultorio.tenant.id,
        email=EMAIL_DUENO,
        roles=["profesional"],
        tipo="access",
        ahora=ahora,
    )


def test_el_401_de_auth_conserva_cabeceras_cors(entorno: Entorno) -> None:
    """Regresión: el navegador solo puede reintentar el refresh si ve el 401 tipado."""
    respuesta = cliente(entorno.app).get(
        "/panel/demo", headers={"Origin": "http://localhost:5173"}
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert respuesta.headers["access-control-allow-credentials"] == "true"


def test_una_ruta_de_panel_sin_token_es_401_por_defecto(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get("/panel/demo")

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "RN-AU-01"
    assert cuerpo["message"]
    assert cuerpo["details"]["reason"]


def test_una_ruta_de_panel_con_access_valido_pasa(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get(
        "/panel/demo", headers={"Authorization": f"Bearer {_access(entorno)}"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}


def test_un_access_expirado_lo_corta_el_middleware(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get(
        "/panel/demo",
        headers={
            "Authorization": (
                f"Bearer {_access(entorno, ahora=datetime.now(UTC) - timedelta(days=1))}"
            )
        },
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_expirado"


def test_un_refresh_como_bearer_lo_corta_el_middleware(entorno: Entorno) -> None:
    refresh = login(cliente(entorno.app)).cookies.get("refresh_token")
    assert refresh

    respuesta = cliente(entorno.app).get(
        "/panel/demo", headers={"Authorization": f"Bearer {refresh}"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["details"]["reason"] == "token_invalido"


def test_la_allowlist_publica_no_exige_jwt(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    assert client.get("/turnero/ping").status_code == 200
    assert client.get("/health").status_code == 200


def test_el_401_del_middleware_usa_el_sobre_de_error(entorno: Entorno) -> None:
    respuesta = cliente(entorno.app).get("/panel/demo")

    assert set(respuesta.json()) <= {"code", "message", "details"}
    assert respuesta.json()["code"] == "RN-AU-01"


def test_el_middleware_de_auth_queda_dentro_del_de_tenant(app_env: None) -> None:
    from app.db.session import TenantContextMiddleware
    from app.domain.auth.middleware import AuthMiddleware

    app = _app_con_rutas_de_panel()[0]
    orden = [middleware.cls for middleware in app.user_middleware]

    assert orden.index(TenantContextMiddleware) < orden.index(AuthMiddleware)


def test_el_tenant_se_resuelve_antes_que_auth(
    entorno: Entorno, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings
    from app.db.session import reset_tenant_cache

    monkeypatch.setenv("TENANT_DEFAULT_SLUG", "inexistente")
    get_settings.cache_clear()
    reset_tenant_cache()

    respuesta = cliente(entorno.app).get("/panel/demo")

    assert respuesta.status_code == 503
