"""Humo del harness de integración: base dedicada, migrada y distinta de la de dev."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine


@pytest.mark.integration
def test_harness_conecta_a_una_base_de_test(db_engine: Engine, db_url: str) -> None:
    with db_engine.connect() as conn:
        actual = conn.execute(text("SELECT current_database()")).scalar_one()
    assert actual == "turnos_test"
    assert db_url.endswith("/turnos_test")
    assert actual != "turnos"


@pytest.mark.integration
def test_harness_dejo_las_migraciones_aplicadas(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0002_tenancy_usuario"
