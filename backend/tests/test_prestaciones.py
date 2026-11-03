"""Catálogo de prestaciones: CRUD dueño-only, duración RN-AG-03 y aislamiento."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Prestacion, RolUsuario, Tenant
from tests.auth_helpers import (
    EMAIL_RECEPCION,
    PASSWORD,
    Consultorio,
    app_de_prueba,
    autorizacion,
    cliente,
    crear_consultorio,
)
from tests.factories import (
    crear_prestacion,
    crear_tenant,
    crear_usuario_con_password,
)

pytestmark = pytest.mark.integration


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
            "profesional@demo",
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
        )
    app, _ = app_de_prueba()
    return Entorno(app=app, consultorio=consultorio)


@pytest.fixture()
def dueno_auth(entorno: Entorno) -> dict[str, str]:
    return autorizacion(entorno.app)


def _crear(client: object, auth: dict[str, str], **cuerpo: object) -> object:
    return client.post("/prestaciones", json=cuerpo, headers=auth)  # type: ignore[attr-defined]


def test_el_dueno_lista_crea_edita_y_desactiva_prestaciones(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)

    vacio = client.get("/prestaciones", headers=dueno_auth)
    assert vacio.status_code == 200
    assert vacio.json() == []

    creada = _crear(client, dueno_auth, nombre="Consulta", duracion_min=30)
    assert creada.status_code == 201
    cuerpo = creada.json()
    assert cuerpo["nombre"] == "Consulta"
    assert cuerpo["duracion_min"] == 30
    assert cuerpo["activa"] is True
    prestacion_id = cuerpo["id"]

    listado = client.get("/prestaciones", headers=dueno_auth)
    assert listado.status_code == 200
    assert [p["id"] for p in listado.json()] == [prestacion_id]

    editada = client.patch(
        f"/prestaciones/{prestacion_id}", json={"duracion_min": 45}, headers=dueno_auth
    )
    assert editada.status_code == 200
    assert editada.json()["duracion_min"] == 45

    desactivada = client.post(f"/prestaciones/{prestacion_id}/desactivar", headers=dueno_auth)
    assert desactivada.status_code == 200
    assert desactivada.json()["activa"] is False

    activas = client.get("/prestaciones?activa=true", headers=dueno_auth)
    assert activas.status_code == 200
    assert activas.json() == []


def test_el_listado_ordena_por_nombre_y_aisla_por_tenant(
    entorno: Entorno,
    dueno_auth: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        crear_prestacion(session, tenant, nombre="Zeta", duracion_min=30)
        crear_prestacion(session, tenant, nombre="Alfa", duracion_min=20)
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        crear_prestacion(session, otro, nombre="Ajeno", duracion_min=30)

    respuesta = cliente(entorno.app).get("/prestaciones", headers=dueno_auth)

    assert respuesta.status_code == 200
    assert [p["nombre"] for p in respuesta.json()] == ["Alfa", "Zeta"]


@pytest.mark.parametrize("duracion", [0, -5, 33])
def test_duracion_invalida_al_crear_responde_422_sin_persistir(
    entorno: Entorno, dueno_auth: dict[str, str], duracion: int
) -> None:
    client = cliente(entorno.app)

    respuesta = _crear(client, dueno_auth, nombre="Inválida", duracion_min=duracion)

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "RN-AG-03"
    assert client.get("/prestaciones", headers=dueno_auth).json() == []


def test_duracion_invalida_al_editar_responde_422_sin_persistir(
    entorno: Entorno, dueno_auth: dict[str, str], session_factory: sessionmaker[Session]
) -> None:
    client = cliente(entorno.app)
    creada = _crear(client, dueno_auth, nombre="Consulta", duracion_min=30).json()

    respuesta = client.patch(
        f"/prestaciones/{creada['id']}", json={"duracion_min": 33}, headers=dueno_auth
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "RN-AG-03"
    detalle = client.get("/prestaciones", headers=dueno_auth).json()
    assert detalle[0]["duracion_min"] == 30


def _prestacion_existente(client: object, auth: dict[str, str]) -> dict[str, object]:
    respuesta = client.post(  # type: ignore[attr-defined]
        "/prestaciones", json={"nombre": "Consulta", "duracion_min": 30}, headers=auth
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def test_la_recepcion_recibe_403_y_no_modifica_prestaciones(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)
    prestacion = _prestacion_existente(client, dueno_auth)
    recepcion = autorizacion(entorno.app, EMAIL_RECEPCION)

    crear = client.post(
        "/prestaciones", json={"nombre": "Otra", "duracion_min": 20}, headers=recepcion
    )
    editar = client.patch(
        f"/prestaciones/{prestacion['id']}", json={"duracion_min": 45}, headers=recepcion
    )
    desactivar = client.post(f"/prestaciones/{prestacion['id']}/desactivar", headers=recepcion)

    assert [crear.status_code, editar.status_code, desactivar.status_code] == [403, 403, 403]
    for respuesta in (crear, editar, desactivar):
        assert respuesta.json()["code"] == "RN-AU-02"
    actual = client.get(f"/prestaciones/{prestacion['id']}", headers=dueno_auth).json()
    assert actual["duracion_min"] == 30
    assert actual["activa"] is True


def test_un_profesional_sin_flag_recibe_403(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    prestacion = _prestacion_existente(client, dueno_auth)
    profesional = autorizacion(entorno.app, "profesional@demo")

    crear = client.post(
        "/prestaciones", json={"nombre": "Otra", "duracion_min": 20}, headers=profesional
    )
    editar = client.patch(
        f"/prestaciones/{prestacion['id']}", json={"duracion_min": 45}, headers=profesional
    )

    assert [crear.status_code, editar.status_code] == [403, 403]
    assert client.get("/prestaciones", headers=dueno_auth).json()[0]["duracion_min"] == 30


def test_sin_token_recibe_401(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    listado = client.get("/prestaciones")
    creacion = client.post("/prestaciones", json={"nombre": "Consulta", "duracion_min": 30})
    edicion = client.patch(f"/prestaciones/{uuid.uuid4()}", json={"duracion_min": 45})

    assert [listado.status_code, creacion.status_code, edicion.status_code] == [401, 401, 401]


def test_desactivar_dos_veces_es_idempotente(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    prestacion = _prestacion_existente(client, dueno_auth)

    primera = client.post(f"/prestaciones/{prestacion['id']}/desactivar", headers=dueno_auth)
    segunda = client.post(f"/prestaciones/{prestacion['id']}/desactivar", headers=dueno_auth)

    assert [primera.status_code, segunda.status_code] == [200, 200]
    assert primera.json()["activa"] is False
    assert segunda.json()["activa"] is False


def test_delete_no_esta_expuesto_y_no_borra(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    prestacion = _prestacion_existente(client, dueno_auth)

    borrado = client.delete(f"/prestaciones/{prestacion['id']}", headers=dueno_auth)

    assert borrado.status_code == 405
    assert client.get(f"/prestaciones/{prestacion['id']}", headers=dueno_auth).status_code == 200


def test_patch_vacio_no_cambia_nada(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    prestacion = _prestacion_existente(client, dueno_auth)

    respuesta = client.patch(f"/prestaciones/{prestacion['id']}", json={}, headers=dueno_auth)

    assert respuesta.status_code == 200
    assert respuesta.json() == prestacion


def test_precio_nulo_y_con_dos_decimales_es_aceptado(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)

    sin_precio = _crear(client, dueno_auth, nombre="Sin precio", duracion_min=30)
    con_precio = _crear(
        client, dueno_auth, nombre="Con precio", duracion_min=30, precio_ref="1234.50"
    )

    assert sin_precio.status_code == 201
    assert sin_precio.json()["precio_ref"] is None
    assert con_precio.status_code == 201
    assert Decimal(str(con_precio.json()["precio_ref"])) == Decimal("1234.50")


def test_una_prestacion_de_otro_tenant_responde_404_sin_modificarse(
    entorno: Entorno,
    dueno_auth: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajena = crear_prestacion(session, otro, nombre="Ajena", duracion_min=30)
        ajena_id = ajena.id

    client = cliente(entorno.app)
    editar = client.patch(
        f"/prestaciones/{ajena_id}", json={"duracion_min": 45}, headers=dueno_auth
    )
    desactivar = client.post(f"/prestaciones/{ajena_id}/desactivar", headers=dueno_auth)

    assert [editar.status_code, desactivar.status_code] == [404, 404]
    assert editar.json()["code"] == "RN-GL-01"

    with session_factory() as session:
        sin_cambios = session.get(Prestacion, ajena_id)
        assert sin_cambios is not None
        assert sin_cambios.duracion_min == 30
        assert sin_cambios.activa is True
