"""Contrato real de C-04 que consumen las FKs y el alcance de C-06."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration


def test_profesional_expone_las_columnas_y_el_vinculo_unico(db_engine: Engine) -> None:
    inspector = inspect(db_engine)
    columnas = {c["name"]: c for c in inspector.get_columns("profesional")}
    assert {"id", "tenant_id", "usuario_id", "nombre", "activo"} <= columnas.keys()
    assert not columnas["tenant_id"]["nullable"]
    assert columnas["usuario_id"]["nullable"]
    assert any(
        c["column_names"] == ["usuario_id"] for c in inspector.get_unique_constraints("profesional")
    )
    assert any(
        fk["constrained_columns"] == ["tenant_id"] and fk["referred_table"] == "tenant"
        for fk in inspector.get_foreign_keys("profesional")
    )


def test_la_historia_aplicada_incluye_c04_y_c05(db_engine: Engine) -> None:
    with db_engine.connect() as conexion:
        revision = conexion.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    # C-06 conserva la historia: no supone que C-04 siga siendo el head.
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from tests.conftest import BACKEND_DIR

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    historia = {
        r.revision for r in ScriptDirectory.from_config(config).walk_revisions(head=revision)
    }
    assert {"0003_c04_profesional_prestacion", "0004_paciente"} <= historia
