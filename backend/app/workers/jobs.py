"""Jobs RQ: generación de recordatorios (C-11) y export CSV (C-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.recordatorios.service import generar


def ping_job(origen: str = "worker") -> dict[str, str]:
    """Job stub: prueba que el worker toma y ejecuta trabajos de la cola."""
    return {"origen": origen, "ts": datetime.now(UTC).isoformat(), "estado": "ok"}


def generar_recordatorios(ahora: datetime | None = None) -> dict[str, int]:
    """Job horario: crea los recordatorios pendientes de turnos confirmados próximos."""
    return generar(ahora)

