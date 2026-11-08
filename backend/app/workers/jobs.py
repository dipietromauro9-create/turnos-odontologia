"""Jobs RQ: recordatorios (C-11) y exportación CSV (C-12)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.exportacion.generador import generar
from app.domain.recordatorios.service import generar as generar_recordatorios_servicio


def ping_job(origen: str = "worker") -> dict[str, str]:
    """Job stub: prueba que el worker toma y ejecuta trabajos de la cola."""
    return {"origen": origen, "ts": datetime.now(UTC).isoformat(), "estado": "ok"}


def generar_recordatorios(ahora: datetime | None = None) -> dict[str, int]:
    """Job horario: crea los recordatorios pendientes de turnos confirmados próximos."""
    return generar_recordatorios_servicio(ahora)


def exportar_csv(exportacion_id: str, tenant_id: str) -> dict[str, str]:
    """Job on-demand: genera el CSV de una exportación y actualiza su estado."""
    return generar(uuid.UUID(exportacion_id), uuid.UUID(tenant_id))
