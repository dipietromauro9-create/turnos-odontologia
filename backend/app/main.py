"""App FastAPI mínima: GET /health público + CORS restringido + handlers de dominio."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core import settings as settings_module
from app.core.errors import register_handlers
from app.core.logging import configure_logging
from app.db.session import TenantContextMiddleware, get_engine, get_session, ping_database


class HealthResponse(BaseModel):
    """Contrato de GET /health. R1: sin campos extra."""

    model_config = ConfigDict(extra="forbid")

    status: str
    database: str


def session_dep() -> Iterator[Session]:
    """Dependencia de sesión tenant-scoped (falla si no hay tenant resuelto)."""
    yield from get_session()


SessionDep = Annotated[Session, Depends(session_dep)]


def create_app() -> FastAPI:
    configure_logging()
    settings = settings_module.get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        get_engine(settings.database_url)
        settings.log_safe()
        yield

    app = FastAPI(title="Turnos Odontología API", version="0.1.0", lifespan=lifespan)
    register_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantContextMiddleware)

    @app.get("/health")
    def health() -> HealthResponse:
        ok = ping_database()
        return HealthResponse(status="ok", database="up" if ok else "down")

    return app


app = create_app()
