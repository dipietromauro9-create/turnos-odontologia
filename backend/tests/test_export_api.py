"""Exportación CSV asíncrona: solicitud, estado, descarga y reintento."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    EstadoExportacion,
    Exportacion,
    RolUsuario,
    Tenant,
    TipoExportacion,
)
from app.domain.exportacion import service
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_usuario
from tests.test_agenda_api import cabecera
from tests.test_pacientes_turnos_scope import entorno as entorno

pytestmark = pytest.mark.integration

DESDE = datetime(2030, 6, 1, tzinfo=UTC)
HASTA = datetime(2030, 6, 30, tzinfo=UTC)
RANGO = {"desde": DESDE.isoformat(), "hasta": HASTA.isoformat()}


@pytest.fixture()
def client(app_env: None, entorno):
    return cliente(app_de_prueba()[0])


@pytest.fixture(autouse=True)
def _encolado_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "encolar", lambda *_args, **_kwargs: None)


def _crear(
    session_factory: sessionmaker[Session],
    entorno,
    *,
    estado: EstadoExportacion = EstadoExportacion.LISTO,
    contenido: str | None = "contenido csv",
    tipo: TipoExportacion = TipoExportacion.TURNOS,
) -> Exportacion:
    with session_factory() as session:
        fila = Exportacion(
            tenant_id=entorno.base.tenant.id,
            tipo=tipo,
            estado=estado,
            desde=DESDE,
            hasta=HASTA,
            contenido=contenido,
            error="falla ficticia" if estado is EstadoExportacion.FALLIDO else None,
            creado_por=entorno.base.usuario.id,
        )
        session.add(fila)
        session.commit()
        return fila


def test_sin_jwt_es_401(client) -> None:
    assert client.post("/export/turnos.csv", json=RANGO).status_code == 401


def test_solicitar_export_de_turnos_devuelve_202_y_pendiente(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    respuesta = client.post(
        "/export/turnos.csv", json=RANGO, headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 202, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "turnos"
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["descarga_url"] is None
    assert "contenido" not in cuerpo
    with session_factory() as session:
        fila = session.get(Exportacion, uuid.UUID(cuerpo["id"]))
        assert fila is not None and fila.estado is EstadoExportacion.PENDIENTE


def test_solicitar_export_de_pacientes_devuelve_202(
    client, entorno
) -> None:
    respuesta = client.post(
        "/export/pacientes.csv", json={}, headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 202
    assert respuesta.json()["tipo"] == "pacientes"


def test_rango_invalido_es_422_y_no_crea_fila(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    respuesta = client.post(
        "/export/turnos.csv",
        json={"desde": HASTA.isoformat(), "hasta": DESDE.isoformat()},
        headers=cabecera(entorno.base.usuario),
    )
    assert respuesta.status_code == 422
    with session_factory() as session:
        assert session.query(Exportacion).count() == 0


def test_un_profesional_sin_dueno_no_puede_exportar(client, entorno) -> None:
    respuesta = client.post(
        "/export/turnos.csv", json=RANGO, headers=cabecera(entorno.usuario)
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_la_recepcion_no_puede_exportar(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        recepcion = crear_usuario(
            session, entorno.base.tenant, "recepcion@demo", RolUsuario.RECEPCION
        )
    respuesta = client.post(
        "/export/turnos.csv", json=RANGO, headers=cabecera(recepcion)
    )
    assert respuesta.status_code == 403


def test_estado_de_un_export_listo_incluye_descarga(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    fila = _crear(session_factory, entorno)
    respuesta = client.get(
        f"/export/{fila.id}", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "listo"
    assert respuesta.json()["descarga_url"] == f"/export/{fila.id}/archivo"


def test_descargar_un_export_listo_entrega_csv(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    fila = _crear(session_factory, entorno, contenido="# metadata\nid,nombre\n1,ficticio\n")
    respuesta = client.get(
        f"/export/{fila.id}/archivo", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "metadata" in respuesta.text


@pytest.mark.parametrize("estado", [EstadoExportacion.PENDIENTE, EstadoExportacion.PROCESANDO])
def test_descargar_antes_de_terminar_es_409(
    client, entorno, session_factory: sessionmaker[Session], estado: EstadoExportacion
) -> None:
    fila = _crear(session_factory, entorno, estado=estado, contenido=None)
    respuesta = client.get(
        f"/export/{fila.id}/archivo", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "RN-RP-02"


def test_descargar_un_export_fallido_es_409_con_error(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    fila = _crear(session_factory, entorno, estado=EstadoExportacion.FALLIDO, contenido=None)
    respuesta = client.get(
        f"/export/{fila.id}/archivo", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 409
    assert "falla ficticia" in respuesta.json()["message"]


def test_reintentar_un_export_fallido_lo_vuelve_a_pendiente(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    fila = _crear(session_factory, entorno, estado=EstadoExportacion.FALLIDO, contenido=None)
    respuesta = client.post(
        f"/export/{fila.id}/reintentar", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 202
    assert respuesta.json()["estado"] == "pendiente"
    assert respuesta.json()["error"] is None


def test_no_se_reintenta_un_export_listo(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    fila = _crear(session_factory, entorno)
    respuesta = client.post(
        f"/export/{fila.id}/reintentar", headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 409


def test_un_export_de_otro_tenant_es_404(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = Tenant(slug="otro", nombre="Consultorio Otro")
        session.add(otro)
        session.commit()
        ajeno = Exportacion(
            tenant_id=otro.id,
            tipo=TipoExportacion.TURNOS,
            estado=EstadoExportacion.LISTO,
            contenido="ajeno",
        )
        session.add(ajeno)
        session.commit()
        ajeno_id = ajeno.id

    respuesta = client.get(f"/export/{ajeno_id}", headers=cabecera(entorno.base.usuario))
    assert respuesta.status_code == 404


def test_si_redis_cae_la_fila_queda_fallida_y_responde_503(
    client, entorno, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falla(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError("redis caído")

    monkeypatch.setattr(service, "encolar", _falla)

    respuesta = client.post(
        "/export/turnos.csv", json=RANGO, headers=cabecera(entorno.base.usuario)
    )
    assert respuesta.status_code == 503
    with session_factory() as session:
        fila = session.query(Exportacion).one()
        assert fila.estado is EstadoExportacion.FALLIDO
        assert "redis" in (fila.error or "")
