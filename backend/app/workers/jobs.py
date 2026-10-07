"""Jobs RQ provisorios (C-11/C-12 agregan generar_recordatorios y export_csv)."""

from __future__ import annotations

from datetime import UTC, datetime


def ping_job(origen: str = "worker") -> dict[str, str]:
    """Job stub: prueba que el worker toma y ejecuta trabajos de la cola."""
    return {"origen": origen, "ts": datetime.now(UTC).isoformat(), "estado": "ok"}
