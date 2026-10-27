"""Harness de integración: base `turnos_test` dedicada, migrada una vez por sesión.

Los tests marcados con `integration` corren contra Postgres real (citext, CHECK,
EXCLUDE no existen en SQLite). Si no hay base disponible, se omiten para que los
tests unitarios sigan corriendo sin servicio.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.engine.url import URL as SAURL
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://turnos:turnos_dev@localhost:5432/turnos"
_TEST_DB_SUFFIX = "_test"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _base_url() -> SAURL:
    return make_url(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def _test_url() -> SAURL:
    url = _base_url()
    name = url.database or "turnos"
    if not name.endswith(_TEST_DB_SUFFIX):
        name = f"{name}{_TEST_DB_SUFFIX}"
    if not _IDENT_RE.match(name):
        msg = f"Nombre de base de test inválido: {name}"
        raise ValueError(msg)
    return url.set(database=name)


def _ensure_database(url: SAURL) -> None:
    assert url.database is not None
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        engine.dispose()


def _run_migrations(url: SAURL) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    rendered = url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", rendered)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = rendered
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _truncate(engine: Engine) -> None:
    with engine.begin() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        if tables:
            quoted = ", ".join(f'"{name}"' for name in tables)
            conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _test_url()
    try:
        _ensure_database(url)
        _run_migrations(url)
    except (OperationalError, ProgrammingError) as exc:  # pragma: no cover - entorno sin DB
        pytest.skip(f"Postgres no disponible para tests de integración: {exc}")
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Iterator[Engine]:
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield engine
    engine.dispose()


@pytest.fixture()
def clean_db(db_engine: Engine) -> None:
    _truncate(db_engine)


@pytest.fixture(autouse=True)
def _clean_between_integration_tests(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("integration") is not None:
        _truncate(request.getfixturevalue("db_engine"))
        from app.db.session import reset_tenant_cache

        reset_tenant_cache()


@pytest.fixture()
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture()
def tenant_context_factory() -> Callable[..., object]:
    from app.db.session import tenant_context

    return tenant_context


@contextmanager
def _override_database_url(url: str) -> Iterator[None]:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        from app.core.settings import get_settings

        get_settings.cache_clear()
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        from app.core.settings import get_settings

        get_settings.cache_clear()


@pytest.fixture()
def app_db(db_url: str) -> Iterator[str]:
    """Apunta `Settings.database_url` a la base de test (y limpia el cache)."""
    with _override_database_url(db_url):
        yield db_url


APP_ENV: dict[str, str] = {
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "t" * 40,
    "ACCESS_MINUTES": "15",
    "REFRESH_DAYS": "7",
    "TENANT_DEFAULT_SLUG": "demo",
    "TZ": "America/Argentina/Buenos_Aires",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "RECORDATORIO_VENTANA_HS": "24,48",
}


@pytest.fixture()
def app_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Config completa apuntando a `turnos_test` + cache de settings limpio."""
    for key, value in APP_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DATABASE_URL", db_url)
    _clear_settings()
    yield
    _clear_settings()


def _clear_settings() -> None:
    from app.core.settings import get_settings

    get_settings.cache_clear()
