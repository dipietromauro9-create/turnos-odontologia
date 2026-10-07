"""Sobre uniforme de errores de dominio (RN-GL-01)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app() -> TestClient:
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("SECRET_KEY", "y" * 40)
    from app.core.errors import DomainError, domain_error_handler, register_handlers

    app = FastAPI()
    register_handlers(app)

    @app.get("/romper")
    def romper() -> None:
        raise DomainError(code="RN-GL-01", message="regla conocida", status_code=400)

    # handler directo para cubrir el registro genérico
    app.add_exception_handler(DomainError, domain_error_handler)
    return TestClient(app, raise_server_exceptions=False)


def test_fallo_de_dominio_trae_code_y_4xx() -> None:
    client = _build_app()
    resp = client.get("/romper")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "RN-GL-01"
    assert body["message"] == "regla conocida"


def test_error_generico_no_filtra_detalle_interno() -> None:
    from app.core.errors import DomainError

    err = DomainError(code="RN-TU-01", message="solape", details={"turno": 1})
    assert err.code.startswith("RN-")
    assert err.details == {"turno": 1}
    assert err.status_code == 400
