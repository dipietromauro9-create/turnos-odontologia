"""Chequeo de conexión del worker (stub de C-01; jobs reales en C-11/C-12)."""

from __future__ import annotations

from datetime import datetime

from app.workers.jobs import ping_job


def test_ping_job_devuelve_ok() -> None:
    resultado = ping_job(origen="test")
    assert resultado["origen"] == "test"
    assert resultado["estado"] == "ok"
    # triangular: el timestamp es aware y parseable (convención datetimes aware)
    ts = datetime.fromisoformat(resultado["ts"])
    assert ts.tzinfo is not None
