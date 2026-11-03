"""Catálogo de profesionales: CRUD dueño-only, vínculo con usuario y aislamiento."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Profesional, RolUsuario, Tenant, Usuario
from tests.auth_helpers import (
    PASSWORD,
    Consultorio,
    app_de_prueba,
    autorizacion,
    cliente,
    crear_consultorio,
)
from tests.factories import crear_profesional, crear_tenant, crear_usuario_con_password

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    app: FastAPI
    consultorio: Consultorio
    profesional: Usuario


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session, con_recepcion=True)
        profesional = crear_usuario_con_password(
            session,
            consultorio.tenant,
            "profesional@demo",
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
        )
    app, _ = app_de_prueba()
    return Entorno(app=app, consultorio=consultorio, profesional=profesional)


@pytest.fixture()
def dueno_auth(entorno: Entorno) -> dict[str, str]:
    return autorizacion(entorno.app)


def test_el_dueno_lista_crea_y_edita_profesionales(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)

    vacio = client.get("/profesionales", headers=dueno_auth)
    assert vacio.status_code == 200
    assert vacio.json() == []

    creado = client.post(
        "/profesionales",
        json={"nombre": "Dra. Ficticia", "matricula": "MP-1234"},
        headers=dueno_auth,
    )
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["nombre"] == "Dra. Ficticia"
    assert cuerpo["matricula"] == "MP-1234"
    assert cuerpo["usuario_id"] is None
    assert cuerpo["activo"] is True

    listado = client.get("/profesionales", headers=dueno_auth)
    assert listado.status_code == 200
    assert [p["id"] for p in listado.json()] == [cuerpo["id"]]

    editado = client.patch(
        f"/profesionales/{cuerpo['id']}",
        json={"especialidad": "Ortodoncia"},
        headers=dueno_auth,
    )
    assert editado.status_code == 200
    assert editado.json()["especialidad"] == "Ortodoncia"


def test_se_crea_un_profesional_sin_usuario_de_login(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    respuesta = cliente(entorno.app).post(
        "/profesionales", json={"nombre": "Profesional Histórico"}, headers=dueno_auth
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["usuario_id"] is None
    assert respuesta.json()["activo"] is True


def test_se_vincula_un_usuario_profesional_del_mismo_tenant(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    respuesta = cliente(entorno.app).post(
        "/profesionales",
        json={"nombre": "Dra. Vinculada", "usuario_id": str(entorno.profesional.id)},
        headers=dueno_auth,
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["usuario_id"] == str(entorno.profesional.id)


def test_el_listado_filtra_por_activo_y_ordena_por_nombre(
    entorno: Entorno,
    dueno_auth: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        crear_profesional(session, tenant, nombre="Zeta", activo=True)
        crear_profesional(session, tenant, nombre="Alfa", activo=True)
        crear_profesional(session, tenant, nombre="Inactivo", activo=False)

    client = cliente(entorno.app)
    todos = client.get("/profesionales", headers=dueno_auth)
    activos = client.get("/profesionales?activo=true", headers=dueno_auth)
    inactivos = client.get("/profesionales?activo=false", headers=dueno_auth)

    assert [p["nombre"] for p in todos.json()] == ["Alfa", "Inactivo", "Zeta"]
    assert [p["nombre"] for p in activos.json()] == ["Alfa", "Zeta"]
    assert [p["nombre"] for p in inactivos.json()] == ["Inactivo"]


def test_la_desactivacion_por_patch_lo_saca_de_los_activos(
    entorno: Entorno, dueno_auth: dict[str, str], session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        profesional = crear_profesional(session, tenant, nombre="Dra. Baja", activo=True)
        profesional_id = profesional.id

    client = cliente(entorno.app)
    respuesta = client.patch(
        f"/profesionales/{profesional_id}", json={"activo": False}, headers=dueno_auth
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert client.get("/profesionales?activo=true", headers=dueno_auth).json() == []
    assert client.get(f"/profesionales/{profesional_id}", headers=dueno_auth).json()["id"] == str(
        profesional_id
    )


def test_el_listado_aisla_por_tenant(
    entorno: Entorno,
    dueno_auth: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        crear_profesional(session, tenant, nombre="Propio")
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        crear_profesional(session, otro, nombre="Ajeno")

    respuesta = cliente(entorno.app).get("/profesionales", headers=dueno_auth)

    assert respuesta.status_code == 200
    assert [p["nombre"] for p in respuesta.json()] == ["Propio"]


def test_un_profesional_de_otro_tenant_responde_404_sin_modificarse(
    entorno: Entorno,
    dueno_auth: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = crear_profesional(session, otro, nombre="Ajeno", activo=True)
        ajeno_id = ajeno.id

    respuesta = cliente(entorno.app).patch(
        f"/profesionales/{ajeno_id}", json={"nombre": "Cambiado"}, headers=dueno_auth
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "RN-GL-01"
    with session_factory() as session:
        sin_cambios = session.get(Profesional, ajeno_id)
        assert sin_cambios is not None
        assert sin_cambios.nombre == "Ajeno"


def _profesional_existente(client: object, auth: dict[str, str]) -> dict[str, object]:
    respuesta = client.post(  # type: ignore[attr-defined]
        "/profesionales", json={"nombre": "Dra. Base"}, headers=auth
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def test_la_recepcion_recibe_403_en_todo_el_catalogo(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)
    profesional = _profesional_existente(client, dueno_auth)
    recepcion = autorizacion(entorno.app, "recepcion@demo")

    listado = client.get("/profesionales", headers=recepcion)
    creacion = client.post("/profesionales", json={"nombre": "Otra"}, headers=recepcion)
    edicion = client.patch(
        f"/profesionales/{profesional['id']}", json={"nombre": "Cambiada"}, headers=recepcion
    )

    assert [listado.status_code, creacion.status_code, edicion.status_code] == [403, 403, 403]
    for respuesta in (listado, creacion, edicion):
        assert respuesta.json()["code"] == "RN-AU-02"
    assert client.get("/profesionales", headers=dueno_auth).json()[0]["nombre"] == "Dra. Base"


def test_un_profesional_sin_flag_recibe_403(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    profesional = _profesional_existente(client, dueno_auth)
    sin_flag = autorizacion(entorno.app, "profesional@demo")

    creacion = client.post("/profesionales", json={"nombre": "Otra"}, headers=sin_flag)
    edicion = client.patch(
        f"/profesionales/{profesional['id']}", json={"nombre": "Cambiada"}, headers=sin_flag
    )

    assert [creacion.status_code, edicion.status_code] == [403, 403]
    assert client.get("/profesionales", headers=dueno_auth).json()[0]["nombre"] == "Dra. Base"


def test_sin_token_recibe_401(entorno: Entorno) -> None:
    client = cliente(entorno.app)

    listado = client.get("/profesionales")
    creacion = client.post("/profesionales", json={"nombre": "Dra. Fantasma"})
    edicion = client.patch(f"/profesionales/{uuid.uuid4()}", json={"nombre": "Cambiada"})

    assert [listado.status_code, creacion.status_code, edicion.status_code] == [401, 401, 401]


def test_un_usuario_ya_vinculado_responde_409_sin_segunda_fila(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    client = cliente(entorno.app)
    primero = client.post(
        "/profesionales",
        json={"nombre": "Dra. Uno", "usuario_id": str(entorno.profesional.id)},
        headers=dueno_auth,
    )
    assert primero.status_code == 201

    segundo = client.post(
        "/profesionales",
        json={"nombre": "Dra. Dos", "usuario_id": str(entorno.profesional.id)},
        headers=dueno_auth,
    )

    assert segundo.status_code == 409
    assert segundo.json()["code"] == "RN-GL-01"
    assert segundo.json()["details"]["reason"] == "usuario_ya_vinculado"
    assert len(client.get("/profesionales", headers=dueno_auth).json()) == 1


def test_un_usuario_de_recepcion_no_es_vinculable(
    entorno: Entorno, dueno_auth: dict[str, str]
) -> None:
    assert entorno.consultorio.recepcion is not None

    respuesta = cliente(entorno.app).post(
        "/profesionales",
        json={
            "nombre": "Recepción Como Profesional",
            "usuario_id": str(entorno.consultorio.recepcion.id),
        },
        headers=dueno_auth,
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "RN-GL-01"
    assert respuesta.json()["details"]["reason"] == "usuario_no_vinculable"
    assert cliente(entorno.app).get("/profesionales", headers=dueno_auth).json() == []


def test_un_usuario_de_otro_tenant_responde_404(
    entorno: Entorno, dueno_auth: dict[str, str], session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = crear_usuario_con_password(
            session,
            otro,
            "ajeno@otro",
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
        )
        ajeno_id = ajeno.id

    respuesta = cliente(entorno.app).post(
        "/profesionales",
        json={"nombre": "Dra. Ajena", "usuario_id": str(ajeno_id)},
        headers=dueno_auth,
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "RN-GL-01"
    assert cliente(entorno.app).get("/profesionales", headers=dueno_auth).json() == []


def test_delete_no_esta_expuesto_y_no_borra(entorno: Entorno, dueno_auth: dict[str, str]) -> None:
    client = cliente(entorno.app)
    profesional = _profesional_existente(client, dueno_auth)

    borrado = client.delete(f"/profesionales/{profesional['id']}", headers=dueno_auth)

    assert borrado.status_code == 405
    assert client.get(f"/profesionales/{profesional['id']}", headers=dueno_auth).status_code == 200
