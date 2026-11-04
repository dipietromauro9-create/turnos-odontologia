"""Integración del seed C-04 con el esquema real C-06 y su aislamiento de tests."""

from contextlib import contextmanager
from datetime import time

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Disponibilidad, Usuario
from app.db.seed import run_seed
from app.db.session import tenant_context
from app.domain.agenda.disponibilidad import service
from tests import test_seed_catalogo as c04

pytestmark = pytest.mark.integration


def _esquema_real(engine: Engine) -> None:
    inspector = inspect(engine)
    assert inspector.has_table("disponibilidad")
    assert inspector.has_table("bloqueo")
    assert len(inspector.get_check_constraints("disponibilidad")) == 2
    assert len(inspector.get_foreign_keys("disponibilidad")) == 2
    assert inspector.get_unique_constraints("disponibilidad")
    assert inspector.get_indexes("disponibilidad")


@pytest.mark.parametrize("simula_fallo", [False, True])
def test_fixture_c04_restaura_tabla_real_incluso_si_un_caso_falla(
    db_engine: Engine, simula_fallo: bool
) -> None:
    Disponibilidad.__table__.create(db_engine, checkfirst=True)
    ciclo = contextmanager(c04.sin_disponibilidad.__wrapped__)
    if simula_fallo:
        with pytest.raises(RuntimeError, match="fallo ficticio"), ciclo(db_engine):
            assert not inspect(db_engine).has_table("disponibilidad")
            raise RuntimeError("fallo ficticio")
    else:
        with ciclo(db_engine):
            assert not inspect(db_engine).has_table("disponibilidad")
    _esquema_real(db_engine)


def test_seed_existente_siembra_y_expone_diez_franjas_sin_duplicarlas(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    primero = run_seed()
    segundo = run_seed()
    assert primero["disponibilidad_creadas"] == 10
    assert segundo["disponibilidad_creadas"] == 0
    with session_factory() as session:
        dueno = session.execute(select(Usuario).where(Usuario.email == "dueno@demo")).scalar_one()
    with tenant_context(dueno.tenant_id, "demo"):
        filas = service.listar(dueno)
    assert len(filas) == 10
    assert {(f.dia_semana, f.hora_desde, f.hora_hasta) for f in filas} == {
        (dia, desde, hasta)
        for dia in range(5)
        for desde, hasta in ((time(9), time(13)), (time(16), time(20)))
    }
