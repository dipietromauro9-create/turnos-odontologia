"""RN-PA-02: ninguna ruta pública expone la ficha del paciente."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.auth import middleware as auth_middleware
from app.domain.pacientes.schemas import PacienteOut
from tests import test_architecture as guard_arquitectura
from tests.public_boundary import rutas_publicas_que_exponen_pacientes

pytestmark = pytest.mark.integration


def test_la_app_real_no_tiene_rutas_publicas_con_pacientes(
    app_env: None, session_factory: object
) -> None:
    from tests.auth_helpers import app_de_prueba

    app, _ = app_de_prueba()

    assert rutas_publicas_que_exponen_pacientes(app) == []


def test_las_allowlists_publicas_no_incluyen_pacientes() -> None:
    for allowlist in (
        auth_middleware.RUTAS_PUBLICAS,
        guard_arquitectura.RUTAS_PUBLICAS,
    ):
        assert not any("/pacientes" in ruta for ruta in allowlist)
    for prefijos in (
        auth_middleware.PREFIJOS_PUBLICOS,
        guard_arquitectura.PREFIJOS_PUBLICOS,
    ):
        assert not any("/pacientes" in prefijo for prefijo in prefijos)


def test_get_pacientes_sin_token_responde_401(app_env: None, session_factory: object) -> None:
    from sqlalchemy.orm import sessionmaker

    from tests.auth_helpers import app_de_prueba
    from tests.factories import crear_tenant

    assert isinstance(session_factory, sessionmaker)
    with session_factory() as session:
        crear_tenant(session)
    app, _ = app_de_prueba()

    respuesta = TestClient(app).get("/pacientes")

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


def test_detecta_una_ruta_publica_bajo_el_prefijo_de_pacientes() -> None:
    app = FastAPI()

    @app.get("/pacientes/publico")
    def publico() -> dict[str, bool]:
        return {"ok": True}

    expuestas = rutas_publicas_que_exponen_pacientes(app, rutas_publicas={"/pacientes/publico"})

    assert expuestas == ["/pacientes/publico"]


def test_detecta_una_ruta_publica_que_devuelve_paciente_out() -> None:
    app = FastAPI()

    @app.get("/turnero/ficha")
    def ficha() -> PacienteOut:
        raise NotImplementedError

    expuestas = rutas_publicas_que_exponen_pacientes(app)

    assert "/turnero/ficha" in expuestas
    assert "openapi:PacienteOut" in expuestas


def test_las_rutas_publicas_permitidas_siguen_sin_exponer_pacientes() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"status": True}

    @app.get("/turnero/demo")
    def turnero() -> dict[str, bool]:
        return {"status": True}

    assert rutas_publicas_que_exponen_pacientes(app) == []


def test_el_guard_de_arquitectura_sigue_sin_rutas_sin_proteccion(
    app_env: None, session_factory: object
) -> None:
    from tests.auth_helpers import app_de_prueba

    app, _ = app_de_prueba()

    assert guard_arquitectura._rutas_sin_proteccion(app) == []
