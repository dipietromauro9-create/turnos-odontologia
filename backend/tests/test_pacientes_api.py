"""API `/pacientes`: RBAC, contratos 200/201/200, 401/422 y alcance RN-AU-03."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RolUsuario
from tests.auth_helpers import (
    PASSWORD,
    Consultorio,
    app_de_prueba,
    autorizacion,
    cliente,
    crear_consultorio,
)
from tests.factories import crear_usuario_con_password

pytestmark = pytest.mark.integration

EMAIL_PROFESIONAL = "profesional@demo"


@dataclass(frozen=True)
class Entorno:
    app: FastAPI
    consultorio: Consultorio


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session, con_recepcion=True)
        crear_usuario_con_password(
            session,
            consultorio.tenant,
            EMAIL_PROFESIONAL,
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
        )
    app, _ = app_de_prueba()
    return Entorno(app=app, consultorio=consultorio)


@pytest.fixture()
def recepcion_auth(entorno: Entorno) -> dict[str, str]:
    return autorizacion(entorno.app, email="recepcion@demo")


def _payload(**cambios: object) -> dict[str, object]:
    cuerpo: dict[str, object] = {"nombre": "María González", "telefono": "11 4555-0001"}
    cuerpo.update(cambios)
    return cuerpo


def test_la_recepcion_lista_crea_edita_y_lee_la_ficha(
    entorno: Entorno, recepcion_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)

    vacio = client.get("/pacientes", headers=recepcion_auth)
    assert vacio.status_code == 200
    assert vacio.json() == []

    creado = client.post("/pacientes", json=_payload(), headers=recepcion_auth)
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["advertencia"] is None
    assert cuerpo["paciente"]["nombre"] == "María González"
    assert cuerpo["paciente"]["telefono"] == "1145550001"
    paciente_id = cuerpo["paciente"]["id"]

    listado = client.get("/pacientes", headers=recepcion_auth)
    assert listado.status_code == 200
    assert [p["id"] for p in listado.json()] == [paciente_id]

    leido = client.get(f"/pacientes/{paciente_id}", headers=recepcion_auth)
    assert leido.status_code == 200
    assert leido.json()["id"] == paciente_id

    editado = client.patch(
        f"/pacientes/{paciente_id}",
        json={"observaciones": "Solo observaciones"},
        headers=recepcion_auth,
    )
    assert editado.status_code == 200
    assert editado.json()["observaciones"] == "Solo observaciones"
    assert editado.json()["nombre"] == "María González"
    assert editado.json()["telefono"] == "1145550001"


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("get", "/pacientes"),
        ("post", "/pacientes"),
        ("patch", "/pacientes/00000000-0000-0000-0000-000000000001"),
        ("get", "/pacientes/00000000-0000-0000-0000-000000000001"),
    ],
)
def test_sin_token_todas_las_operaciones_responden_401(
    entorno: Entorno, metodo: str, ruta: str
) -> None:
    client = cliente(entorno.app)

    respuesta = getattr(client, metodo)(ruta)

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"nombre": "Sin teléfono"},
        {"telefono": "1145550001"},
        {"nombre": "Con extra", "telefono": "1145550001", "rol": "profesional"},
        {"nombre": "Teléfono corto", "telefono": "123"},
    ],
)
def test_un_payload_invalido_responde_422(
    entorno: Entorno, recepcion_auth: dict[str, str], cuerpo: dict[str, object]
) -> None:
    respuesta = cliente(entorno.app).post("/pacientes", json=cuerpo, headers=recepcion_auth)

    assert respuesta.status_code == 422


def test_un_duplicado_responde_201_con_rn_pa_01(
    entorno: Entorno, recepcion_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)
    client.post("/pacientes", json=_payload(), headers=recepcion_auth)

    repetido = client.post(
        "/pacientes",
        json=_payload(nombre="Otra Persona"),
        headers=recepcion_auth,
    )

    assert repetido.status_code == 201
    advertencia = repetido.json()["advertencia"]
    assert advertencia["codigo"] == "RN-PA-01"
    assert [d["telefono"] for d in advertencia["duplicados"]] == ["1145550001"]


def test_un_id_inexistente_responde_404_con_sobre_de_dominio(
    entorno: Entorno, recepcion_auth: dict[str, str]
) -> None:
    respuesta = cliente(entorno.app).get(
        "/pacientes/00000000-0000-0000-0000-000000000001", headers=recepcion_auth
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "RN-PA-02"
    assert respuesta.json()["details"] == {"reason": "no_encontrado"}


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_limit_y_offset_invalidos_responden_422(
    entorno: Entorno, recepcion_auth: dict[str, str], query: str
) -> None:
    respuesta = cliente(entorno.app).get(f"/pacientes?{query}", headers=recepcion_auth)

    assert respuesta.status_code == 422


def test_el_profesional_sin_flag_no_toca_un_paciente_ajeno(
    entorno: Entorno, recepcion_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)
    ajeno = client.post("/pacientes", json=_payload(), headers=recepcion_auth).json()
    ajeno_id = ajeno["paciente"]["id"]
    auth_profesional = autorizacion(entorno.app, email=EMAIL_PROFESIONAL)

    listado = client.get("/pacientes", headers=auth_profesional)
    assert listado.status_code == 200
    assert listado.json() == []

    leido = client.get(f"/pacientes/{ajeno_id}", headers=auth_profesional)
    assert leido.status_code == 403
    assert leido.json()["code"] == "RN-AU-03"

    editado = client.patch(
        f"/pacientes/{ajeno_id}",
        json={"observaciones": "No permitido"},
        headers=auth_profesional,
    )
    assert editado.status_code == 403
    assert editado.json()["code"] == "RN-AU-03"

    sigue = client.get(f"/pacientes/{ajeno_id}", headers=recepcion_auth)
    assert sigue.json()["observaciones"] is None
