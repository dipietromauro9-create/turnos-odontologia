"""Contexto de tenant + sesiones tenant-scoped (R3: el filtro no se puede olvidar).

`system_session()` es el único acceso sin scope y está acotado a la tabla
`tenant` (resolución del slug y seed). Todo acceso de dominio pasa por
`get_session()` / `tenant_session()` y lleva el `tenant_id` del contexto.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.core import settings as settings_module
from app.db.models import Tenant, TenantMixin


class TenantNotResolvedError(RuntimeError):
    """No hay tenant en el contexto: abortar antes de consultar."""


class TenantNotFoundError(LookupError):
    """El slug configurado no existe en la base."""


class TenantIsolationError(RuntimeError):
    """Intento de leer/escribir filas de otro tenant."""


class SystemSessionScopeError(RuntimeError):
    """La sesión de sistema solo puede tocar la tabla `tenant`."""


@dataclass(frozen=True)
class TenantContext:
    tenant_id: uuid.UUID
    slug: str


PUBLIC_PATHS = frozenset({"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})

_tenant_ctx: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)

_engine_cache: dict[str, Engine] = {}
_tenant_factory_cache: dict[str, sessionmaker[TenantSession]] = {}
_system_factory_cache: dict[str, sessionmaker[SystemSession]] = {}
_tenant_by_slug_cache: dict[tuple[str, str], TenantContext] = {}


def _database_url() -> str:
    return settings_module.get_settings().database_url


def get_engine(database_url: str | None = None) -> Engine:
    """Motor único por URL; la conexión fija la TZ del sistema (RN-GL-03)."""
    url = database_url or _database_url()
    engine = _engine_cache.get(url)
    if engine is None:
        timezone = settings_module.get_settings().tz
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-c timezone={timezone}"},
        )
        _engine_cache[url] = engine
    return engine


def get_tenant_session_factory(database_url: str | None = None) -> sessionmaker[TenantSession]:
    url = database_url or _database_url()
    factory = _tenant_factory_cache.get(url)
    if factory is None:
        factory = sessionmaker(bind=get_engine(url), class_=TenantSession, expire_on_commit=False)
        _tenant_factory_cache[url] = factory
    return factory


def get_system_session_factory(database_url: str | None = None) -> sessionmaker[SystemSession]:
    url = database_url or _database_url()
    factory = _system_factory_cache.get(url)
    if factory is None:
        factory = sessionmaker(bind=get_engine(url), class_=SystemSession, expire_on_commit=False)
        _system_factory_cache[url] = factory
    return factory


def current_tenant() -> TenantContext | None:
    return _tenant_ctx.get()


def require_tenant() -> TenantContext:
    contexto = _tenant_ctx.get()
    if contexto is None:
        raise TenantNotResolvedError(
            "No hay tenant resuelto para esta request: se niega a consultar sin filtro"
        )
    return contexto


@contextmanager
def tenant_context(tenant_id: uuid.UUID, slug: str) -> Iterator[TenantContext]:
    contexto = TenantContext(tenant_id=tenant_id, slug=slug)
    token = _tenant_ctx.set(contexto)
    try:
        yield contexto
    finally:
        _tenant_ctx.reset(token)


def reset_tenant_cache() -> None:
    """Limpia el cache slug→tenant (tests y cambios de base)."""
    _tenant_by_slug_cache.clear()
    for engine in _engine_cache.values():
        engine.dispose()
    _engine_cache.clear()
    _tenant_factory_cache.clear()
    _system_factory_cache.clear()


class TenantSession(Session):
    """Sesión de dominio: filtro automático y guarda de escritura por tenant."""

    def __init__(self, *args: Any, tenant_id: uuid.UUID, **kwargs: Any) -> None:
        self._tenant_id = tenant_id
        super().__init__(*args, **kwargs)

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id


class SystemSession(Session):
    """Acceso sin scope, limitado a la tabla `tenant`."""


@event.listens_for(TenantSession, "do_orm_execute")
def _aplicar_filtro_tenant(execute_state: Any) -> None:
    if not execute_state.is_select:
        return
    tenant_id = execute_state.session.tenant_id
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(TenantSession, "before_flush")
def _guardar_frontera_tenant(session: Session, _ctx: Any, _instances: Any) -> None:
    assert isinstance(session, TenantSession)
    esperado = session.tenant_id
    for obj in (*session.new, *session.dirty, *session.deleted):
        if not isinstance(obj, TenantMixin):
            continue
        actual = getattr(obj, "tenant_id", None)
        if actual != esperado:
            raise TenantIsolationError(
                f"{type(obj).__name__} pertenece a otro tenant ({actual} != {esperado})"
            )


@event.listens_for(SystemSession, "do_orm_execute")
def _limitar_sesion_sistema(execute_state: Any) -> None:
    clases = {mapper.class_ for mapper in execute_state.all_mappers}
    if not clases:
        raise SystemSessionScopeError(
            "La sesión de sistema solo admite consultas ORM sobre la tabla tenant"
        )
    if clases - {Tenant}:
        raise SystemSessionScopeError("La sesión de sistema no puede consultar tablas de dominio")


@event.listens_for(SystemSession, "before_flush")
def _limitar_escritura_sistema(session: Session, _ctx: Any, _instances: Any) -> None:
    for obj in (*session.new, *session.dirty, *session.deleted):
        if not isinstance(obj, Tenant):
            raise SystemSessionScopeError(
                "La sesión de sistema solo puede escribir la tabla tenant"
            )


def resolve_tenant(slug: str) -> TenantContext:
    """Resuelve (con cache) el tenant configurado usando la sesión de sistema."""
    url = _database_url()
    key = (url, slug)
    cached = _tenant_by_slug_cache.get(key)
    if cached is not None:
        return cached

    with system_session() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()

    if tenant is None:
        raise TenantNotFoundError(f"El tenant configurado '{slug}' no existe")
    contexto = TenantContext(tenant_id=tenant.id, slug=tenant.slug)
    _tenant_by_slug_cache[key] = contexto
    return contexto


@contextmanager
def system_session() -> Iterator[SystemSession]:
    with get_system_session_factory()() as session:
        yield session


@contextmanager
def tenant_session(tenant_id: uuid.UUID) -> Iterator[TenantSession]:
    with get_tenant_session_factory()(tenant_id=tenant_id) as session:
        yield session


def get_session() -> Iterator[TenantSession]:
    """Dependencia FastAPI: sesión scoped al tenant resuelto o falla (R3)."""
    contexto = require_tenant()
    with get_tenant_session_factory()(tenant_id=contexto.tenant_id) as session:
        yield session


def ping_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


class TenantContextMiddleware:
    """Resuelve `TENANT_DEFAULT_SLUG` y publica el contexto en el ContextVar."""

    def __init__(self, app: Any, default_slug: str | None = None) -> None:
        self.app = app
        self._default_slug = default_slug

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        from fastapi.responses import JSONResponse

        slug = self._default_slug or settings_module.get_settings().tenant_default_slug
        try:
            contexto = resolve_tenant(slug)
        except TenantNotFoundError as exc:
            respuesta = JSONResponse(status_code=503, content={"detail": str(exc)})
            await respuesta(scope, receive, send)
            return

        token = _tenant_ctx.set(contexto)
        try:
            await self.app(scope, receive, send)
        finally:
            _tenant_ctx.reset(token)
