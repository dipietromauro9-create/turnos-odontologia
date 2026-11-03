"""Guardias de arquitectura: dominio sin SQL crudo y modelos con frontera de tenant."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from app.db.base import Base
from app.db.models import Tenant, TenantMixin

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"
AGENDA_DIR = DOMAIN_DIR / "agenda"
SQL_CRUDO = re.compile(r"\btext\s*\(")
BULK = re.compile(r"\bbulk_")
TURNO = re.compile(r"\bTurno\b")

RUTAS_PUBLICAS = frozenset(
    {
        "/health",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
    }
)
PREFIJOS_PUBLICOS = ("/turnero/",)

APP_PANEL_ENV = {
    "DATABASE_URL": "postgresql+psycopg://turnos:turnos_dev@localhost:5432/turnos_test",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "t" * 40,
    "ACCESS_MINUTES": "15",
    "REFRESH_DAYS": "7",
    "TENANT_DEFAULT_SLUG": "demo",
    "TZ": "America/Argentina/Buenos_Aires",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "RECORDATORIO_VENTANA_HS": "24,48",
}


def _es_ruta_publica(path: str) -> bool:
    if path in RUTAS_PUBLICAS:
        return True
    return path == "/turnero" or path.startswith(PREFIJOS_PUBLICOS)


def _declara_proteccion(dependencia: object) -> bool:
    call = getattr(dependencia, "call", None)
    if getattr(call, "__requiere_auth__", False) or getattr(call, "__rbac_roles__", None):
        return True
    return any(_declara_proteccion(sub) for sub in getattr(dependencia, "dependencies", ()))


def _rutas_sin_proteccion(app: FastAPI) -> list[str]:
    """Rutas de panel que ni autentican ni declaran roles (falla cerrado)."""
    return sorted(
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and not _es_ruta_publica(route.path)
        and not _declara_proteccion(route.dependant)
    )


def _fuentes_de_dominio() -> list[Path]:
    return sorted(DOMAIN_DIR.rglob("*.py"))


def test_app_domain_no_usa_sql_crudo_ni_bulk() -> None:
    archivos = _fuentes_de_dominio()
    assert archivos, "app/domain debe existir y contener código de dominio"

    infracciones: list[str] = []
    for archivo in archivos:
        fuente = archivo.read_text(encoding="utf-8")
        if SQL_CRUDO.search(fuente) or BULK.search(fuente):
            infracciones.append(str(archivo.relative_to(DOMAIN_DIR)))
    assert infracciones == []


def test_todo_modelo_de_dominio_usa_tenant_mixin() -> None:
    modelos = {mapper.class_ for mapper in Base.registry.mappers}
    dominio = modelos - {Tenant}

    assert dominio, "debe haber al menos un modelo de dominio además de Tenant"
    sin_mixin = sorted(modelo.__name__ for modelo in dominio if not issubclass(modelo, TenantMixin))
    assert sin_mixin == []


def _archivos_con_patron(directorio: Path, patron: re.Pattern[str]) -> list[str]:
    if not directorio.exists():
        return []
    return [
        str(archivo.relative_to(DOMAIN_DIR))
        for archivo in sorted(directorio.rglob("*.py"))
        if patron.search(archivo.read_text(encoding="utf-8"))
    ]


def infracciones_turno_en_agenda() -> list[str]:
    """RN-AG-03: el catálogo no puede importar ni escribir `Turno` (llega en C-07)."""
    return _archivos_con_patron(AGENDA_DIR, TURNO)


def test_el_dominio_de_agenda_no_referencia_turno() -> None:
    assert infracciones_turno_en_agenda() == []


@pytest.fixture()
def app_del_panel(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    for key, value in APP_PANEL_ENV.items():
        monkeypatch.setenv(key, value)
    from app.core.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    yield create_app()
    get_settings.cache_clear()


def test_toda_ruta_no_publica_declara_autenticacion_y_roles(app_del_panel: FastAPI) -> None:
    assert _rutas_sin_proteccion(app_del_panel) == []


def test_el_guard_ignora_la_allowlist_publica() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"status": True}

    @app.get("/turnero/demo")
    def turnero() -> dict[str, bool]:
        return {"status": True}

    assert _rutas_sin_proteccion(app) == []


def test_el_guard_acepta_una_ruta_con_roles() -> None:
    from app.db.models import RolUsuario
    from app.domain.auth.dependencies import require_role

    app = FastAPI()

    @app.get("/panel/protegida", dependencies=[Depends(require_role(RolUsuario.PROFESIONAL))])
    def protegida() -> dict[str, bool]:
        return {"ok": True}

    assert _rutas_sin_proteccion(app) == []


def test_el_guard_detecta_una_ruta_de_panel_sin_proteccion() -> None:
    app = FastAPI()

    @app.get("/panel/sin-proteccion")
    def sin_proteccion() -> dict[str, bool]:
        return {"ok": True}

    assert _rutas_sin_proteccion(app) == ["/panel/sin-proteccion"]
