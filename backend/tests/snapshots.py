"""Snapshots de tablas de dominio para tests de invariantes (RN-AG-03 y afines)."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

TABLAS_DOMINIO: tuple[str, ...] = ("tenant", "usuario", "profesional", "prestacion")


def snapshot_tablas(
    engine: Engine, tablas: tuple[str, ...] = TABLAS_DOMINIO
) -> dict[str, list[dict[str, object]]]:
    """Foto ordenada de las filas de cada tabla, apta para comparar antes/después."""
    foto: dict[str, list[dict[str, object]]] = {}
    with engine.connect() as conexion:
        for tabla in tablas:
            filas = conexion.execute(text(f'SELECT * FROM "{tabla}" ORDER BY id')).mappings().all()
            foto[tabla] = [dict(fila) for fila in filas]
    return foto


def fila(
    foto: dict[str, list[dict[str, object]]], tabla: str, entidad_id: object
) -> dict[str, object]:
    """Devuelve la fila con ese id dentro del snapshot."""
    objetivo = uuid.UUID(str(entidad_id))
    return next(item for item in foto[tabla] if item["id"] == objetivo)


def columnas_modificadas(vieja: dict[str, object], nueva: dict[str, object]) -> set[str]:
    """Columnas con cambio real; `actualizado_en` se audita aparte."""
    return {
        columna
        for columna in vieja
        if vieja[columna] != nueva[columna] and columna != "actualizado_en"
    }
