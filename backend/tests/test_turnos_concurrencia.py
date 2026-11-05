"""Carreras reales: ambas transacciones superan la consulta de ocupación."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, local

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import Turno
from app.db.session import tenant_context
from app.domain.turnos.repository import TurnosRepository
from app.domain.turnos.schemas import TurnoCreate
from app.domain.turnos.service import crear
from tests.turnos_factories import AHORA, INICIO, entorno_turnos

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("contiguos", [False, True])
def test_dos_transacciones_no_confian_solo_en_la_consulta_previa(
    app_env: None,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    contiguos: bool,
) -> None:
    with session_factory() as session:
        entorno = entorno_turnos(session)
    barrera = Barrier(2)
    hilo = local()
    original = TurnosRepository.ocupado

    def consultar_y_esperar(self, *args, **kwargs):
        ocupado = original(self, *args, **kwargs)
        if not getattr(hilo, "consultado", False):
            assert ocupado is False
            hilo.consultado = True
            barrera.wait(timeout=10)
        return ocupado

    monkeypatch.setattr(TurnosRepository, "ocupado", consultar_y_esperar)

    def reservar(indice: int) -> str:
        inicio = INICIO + timedelta(minutes=30 * indice if contiguos else 0)
        try:
            with tenant_context(entorno.tenant.id, "demo"):
                crear(TurnoCreate(**entorno.datos(inicio=inicio)), entorno.usuario, ahora=AHORA)
            return "creado"
        except DomainError as exc:
            return exc.code
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(reservar, [0, 1]))
    assert sorted(resultados) == (["creado", "creado"] if contiguos else ["RN-TU-01", "creado"])
    with session_factory() as session:
        assert session.query(Turno).count() == (2 if contiguos else 1)
