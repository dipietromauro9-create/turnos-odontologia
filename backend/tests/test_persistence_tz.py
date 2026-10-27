"""Zona horaria única de persistencia (RN-GL-03)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import get_engine

pytestmark = pytest.mark.integration


def test_la_conexion_usa_la_zona_del_sistema(app_env: None) -> None:
    with get_engine().connect() as conexion:
        zona = conexion.execute(text("SHOW timezone")).scalar_one()

    assert zona == "America/Argentina/Buenos_Aires"
