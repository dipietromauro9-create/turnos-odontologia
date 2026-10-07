"""App FastAPI mínima: GET /health público + CORS restringido + handlers de dominio."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.errors import register_handlers
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.db.base import get_engine, ping_database


class HealthResponse(BaseModel):
    """Contrato de GET /health. R1: sin campos extra."""

    model_config = ConfigDict(extra="forbid")

    status: str
    database: str


def session_dep() -> Iterator[Session]:
    """Dependencia de sesión a nivel módulo (alias reutilizable, estilo Annotated)."""
    from app.db.base import get_session

    yield from get_session(get_settings().database_url)


SessionDep = Annotated[Session, Depends(session_dep)]


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

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

    @app.get("/health")
    def health(session: SessionDep) -> HealthResponse:
        ok = ping_database(session)
        return HealthResponse(status="ok", database="up" if ok else "down")

    return app


app = create_app()
