"""RN-AG-03: cambiar la duración de una prestación no puede tocar ninguna otra fila.

El extremo a extremo (``fin`` congelado por turno) se completa en C-07; acá se
verifica el invariante de catálogo: el ``PATCH`` de ``duracion_min`` escribe una
sola fila y las FKs del catálogo no declaran cascadas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Prestacion, Profesional
from tests.auth_helpers import (
    Consultorio,
    app_de_prueba,
    autorizacion,
    cliente,
    crear_consultorio,
)
from tests.snapshots import columnas_modificadas, fila, snapshot_tablas

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    app: FastAPI
    consultorio: Consultorio


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        consultorio = crear_consultorio(session, con_recepcion=True)
    app, _ = app_de_prueba()
    return Entorno(app=app, consultorio=consultorio)


def _crear_prestacion(client: object, auth: dict[str, str], duracion: int) -> dict[str, object]:
    respuesta = client.post(  # type: ignore[attr-defined]
        "/prestaciones",
        json={"nombre": "Consulta de control", "duracion_min": duracion},
        headers=auth,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _verificar_solo_cambio(
    antes: dict[str, list[dict[str, object]]],
    despues: dict[str, list[dict[str, object]]],
    *,
    tabla: str,
    entidad_id: object,
    columnas: set[str],
) -> None:
    for otra in ("tenant", "usuario", "profesional", "prestacion"):
        if otra != tabla:
            assert despues[otra] == antes[otra], f"el PATCH tocó la tabla {otra}"
    assert len(despues[tabla]) == len(antes[tabla])
    objetivo = uuid.UUID(str(entidad_id))
    for vieja, nueva in zip(antes[tabla], despues[tabla], strict=True):
        if vieja["id"] != objetivo:
            assert nueva == vieja, f"el PATCH modificó otra fila de {tabla}"
    assert (
        columnas_modificadas(fila(antes, tabla, entidad_id), fila(despues, tabla, entidad_id))
        == columnas
    )


def test_cambiar_duracion_solo_modifica_la_fila_de_la_prestacion(
    entorno: Entorno, db_engine: Engine
) -> None:
    client = cliente(entorno.app)
    auth = autorizacion(entorno.app)
    prestacion = _crear_prestacion(client, auth, 30)

    antes = snapshot_tablas(db_engine)
    respuesta = client.patch(
        f"/prestaciones/{prestacion['id']}",
        json={"duracion_min": 45},
        headers=auth,
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["duracion_min"] == 45
    despues = snapshot_tablas(db_engine)

    _verificar_solo_cambio(
        antes,
        despues,
        tabla="prestacion",
        entidad_id=prestacion["id"],
        columnas={"duracion_min"},
    )
    nueva = fila(despues, "prestacion", prestacion["id"])
    vieja = fila(antes, "prestacion", prestacion["id"])
    assert nueva["duracion_min"] == 45
    assert nueva["creado_en"] == vieja["creado_en"]
    assert nueva["nombre"] == vieja["nombre"]
    assert nueva["precio_ref"] == vieja["precio_ref"]
    assert nueva["activa"] == vieja["activa"]


def test_las_fks_del_catalogo_no_declaran_cascadas() -> None:
    tablas = {Profesional.__tablename__, Prestacion.__tablename__}
    infracciones: list[str] = []
    for tabla in Base.metadata.tables.values():
        if tabla.name not in tablas:
            continue
        for clave in tabla.foreign_keys:
            for accion in (clave.onupdate, clave.ondelete):
                if accion is not None and accion.upper() == "CASCADE":
                    infracciones.append(f"{tabla.name}.{clave.parent.name}={accion}")
    assert infracciones == []


def test_la_guarda_de_arquitectura_cubre_el_dominio_de_agenda() -> None:
    from tests.test_architecture import infracciones_turno_en_agenda

    assert infracciones_turno_en_agenda() == []


def test_cambiar_precio_ref_no_altera_duraciones_ni_otras_filas(
    entorno: Entorno, db_engine: Engine
) -> None:
    client = cliente(entorno.app)
    auth = autorizacion(entorno.app)
    prestacion = _crear_prestacion(client, auth, 30)

    antes = snapshot_tablas(db_engine)
    respuesta = client.patch(
        f"/prestaciones/{prestacion['id']}",
        json={"precio_ref": "1500.50"},
        headers=auth,
    )
    assert respuesta.status_code == 200, respuesta.text
    despues = snapshot_tablas(db_engine)

    _verificar_solo_cambio(
        antes,
        despues,
        tabla="prestacion",
        entidad_id=prestacion["id"],
        columnas={"precio_ref"},
    )
    assert fila(despues, "prestacion", prestacion["id"])["duracion_min"] == 30


def test_cambiar_datos_del_profesional_no_altera_duraciones(
    entorno: Entorno, db_engine: Engine
) -> None:
    client = cliente(entorno.app)
    auth = autorizacion(entorno.app)
    prestacion = _crear_prestacion(client, auth, 30)
    creado = client.post(
        "/profesionales",
        json={"nombre": "Profesional Ficticio", "matricula": "MP-0001"},
        headers=auth,
    )
    assert creado.status_code == 201, creado.text
    profesional_id = creado.json()["id"]

    antes = snapshot_tablas(db_engine)
    respuesta = client.patch(
        f"/profesionales/{profesional_id}",
        json={"nombre": "Profesional Renombrado", "especialidad": "Ortodoncia"},
        headers=auth,
    )
    assert respuesta.status_code == 200, respuesta.text
    despues = snapshot_tablas(db_engine)

    _verificar_solo_cambio(
        antes,
        despues,
        tabla="profesional",
        entidad_id=profesional_id,
        columnas={"nombre", "especialidad"},
    )
    assert fila(despues, "prestacion", prestacion["id"])["duracion_min"] == 30


def test_una_prestacion_desactivada_sigue_consultable_por_id(
    entorno: Entorno,
) -> None:
    client = cliente(entorno.app)
    auth = autorizacion(entorno.app)
    prestacion = _crear_prestacion(client, auth, 30)

    desactivada = client.post(f"/prestaciones/{prestacion['id']}/desactivar", headers=auth)
    assert desactivada.status_code == 200, desactivada.text
    assert desactivada.json()["activa"] is False

    por_id = client.get(f"/prestaciones/{prestacion['id']}", headers=auth)
    assert por_id.status_code == 200, por_id.text
    assert por_id.json()["duracion_min"] == 30

    activas = client.get("/prestaciones", params={"activa": True}, headers=auth)
    assert activas.status_code == 200
    assert [item["id"] for item in activas.json()] == []
