"""API interna de huecos: JWT, RBAC de panel, contrato sin PII y ruta de plantilla."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    EstadoTurno,
    Paciente,
    Prestacion,
    Profesional,
    RolUsuario,
    Tenant,
    Turno,
    Usuario,
)
from tests.agenda_factories import crear_disponibilidad
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_prestacion, crear_profesional, crear_tenant, crear_usuario
from tests.test_agenda_api import cabecera

pytestmark = pytest.mark.integration

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2030, 6, 3)
MARTES = LUNES + timedelta(days=1)
DESDE = datetime.combine(LUNES, time(0), TZ)
HASTA = datetime.combine(MARTES, time(0), TZ)


@dataclass(frozen=True)
class Entorno:
    tenant: Tenant
    otro_tenant: Tenant
    profesional: Profesional
    segundo: Profesional
    sin_agenda: Profesional
    ajeno: Profesional
    dueno: Usuario
    recepcion: Usuario
    usuario: Usuario
    sin_vinculo: Usuario
    prestacion: Prestacion
    prestacion_inactiva: Prestacion
    prestacion_ajena: Prestacion
    paciente: Paciente


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[Entorno]:
    with session_factory() as session:
        tenant = crear_tenant(session)
        otro_tenant = crear_tenant(session, "otro")
        dueno = crear_usuario(session, tenant, "dueno@demo", RolUsuario.PROFESIONAL, es_dueno=True)
        recepcion = crear_usuario(session, tenant, "recepcion@demo")
        usuario = crear_usuario(session, tenant, "profesional@demo", RolUsuario.PROFESIONAL)
        sin_vinculo = crear_usuario(session, tenant, "sinvinculo@demo", RolUsuario.PROFESIONAL)
        profesional = crear_profesional(session, tenant, usuario=usuario)
        segundo = crear_profesional(session, tenant, nombre="Segundo Ficticio")
        sin_agenda = crear_profesional(session, tenant, nombre="Sin Agenda Ficticio")
        ajeno = crear_profesional(session, otro_tenant, nombre="Ajeno Ficticio")
        prestacion = crear_prestacion(session, tenant, duracion_min=30)
        prestacion_inactiva = crear_prestacion(
            session, tenant, nombre="Inactiva Ficticia", activa=False
        )
        prestacion_ajena = crear_prestacion(session, otro_tenant, nombre="Ajena Ficticia")
        paciente = Paciente(
            tenant_id=tenant.id,
            nombre="Paciente Ficticio",
            telefono="1145550001",
        )
        session.add(paciente)
        session.commit()
        crear_disponibilidad(session, tenant, profesional, dia_semana=0, hora_desde=time(9))
        crear_disponibilidad(session, tenant, segundo, dia_semana=0, hora_desde=time(9))
        yield Entorno(
            tenant,
            otro_tenant,
            profesional,
            segundo,
            sin_agenda,
            ajeno,
            dueno,
            recepcion,
            usuario,
            sin_vinculo,
            prestacion,
            prestacion_inactiva,
            prestacion_ajena,
            paciente,
        )


@pytest.fixture()
def app(entorno: Entorno) -> FastAPI:
    return app_de_prueba()[0]


def params(
    entorno: Entorno,
    *,
    profesional: Profesional | None = None,
    prestacion: Prestacion | None = None,
    desde: datetime = DESDE,
    hasta: datetime = HASTA,
) -> dict[str, str]:
    return {
        "profesional_id": str((profesional or entorno.profesional).id),
        "prestacion_id": str((prestacion or entorno.prestacion).id),
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
    }


# --- Grupo 5: contrato HTTP básico (RN-AG-04, RN-AU-03) ---


def test_sin_jwt_es_401(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get("/disponibilidad/huecos", params=params(entorno))
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


@pytest.mark.parametrize("actor", ["dueno", "recepcion"])
def test_recepcion_y_dueno_consultan_cualquier_profesional(
    app: FastAPI, entorno: Entorno, actor: str
) -> None:
    usuario = entorno.dueno if actor == "dueno" else entorno.recepcion
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, profesional=entorno.segundo),
        headers=cabecera(usuario),
    )
    assert respuesta.status_code == 200
    huecos = respuesta.json()
    assert huecos
    assert {h["profesional_id"] for h in huecos} == {str(entorno.segundo.id)}


def test_profesional_sin_flag_consulta_su_propia_agenda(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno),
        headers=cabecera(entorno.usuario),
    )
    assert respuesta.status_code == 200
    assert {h["profesional_id"] for h in respuesta.json()} == {str(entorno.profesional.id)}


def test_profesional_sin_flag_por_otro_es_403(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, profesional=entorno.segundo),
        headers=cabecera(entorno.usuario),
    )
    assert respuesta.status_code == 403
    assert respuesta.json() == {
        "code": "RN-AU-03",
        "message": "Solo puede consultar su propia agenda",
        "details": {"reason": "fuera_de_alcance"},
    }


def test_codigo_publico_sin_jwt_no_autentica(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params={**params(entorno), "codigo_publico": "COD000000001"},
    )
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


@pytest.mark.parametrize("faltante", ["profesional_id", "prestacion_id", "desde", "hasta"])
def test_parametros_obligatorios(app: FastAPI, entorno: Entorno, faltante: str) -> None:
    datos = params(entorno)
    datos.pop(faltante)
    respuesta = cliente(app).get(
        "/disponibilidad/huecos", params=datos, headers=cabecera(entorno.recepcion)
    )
    assert respuesta.status_code == 422


def test_agenda_sin_franjas_devuelve_lista_vacia(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, profesional=entorno.sin_agenda),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_la_respuesta_no_contiene_datos_de_pacientes(
    app: FastAPI, entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        session.add(
            Turno(
                tenant_id=entorno.tenant.id,
                profesional_id=entorno.profesional.id,
                paciente_id=entorno.paciente.id,
                prestacion_id=entorno.prestacion.id,
                inicio=datetime.combine(LUNES, time(9), TZ),
                fin=datetime.combine(LUNES, time(9, 30), TZ),
                estado=EstadoTurno.RESERVADO,
                codigo_publico="COD000000001",
            )
        )
        session.commit()

    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200
    huecos = respuesta.json()
    assert huecos
    for hueco in huecos:
        assert set(hueco) == {"inicio", "fin", "profesional_id", "prestacion_id"}
    assert "Paciente Ficticio" not in respuesta.text
    assert "1145550001" not in respuesta.text
    assert [h for h in huecos if h["inicio"] == "2030-06-03T09:00:00-03:00"] == []


def test_get_disponibilidad_de_plantilla_conserva_su_contrato(
    app: FastAPI, entorno: Entorno
) -> None:
    client = cliente(app)
    auth = cabecera(entorno.recepcion)
    filtrada = client.get(
        f"/disponibilidad?profesional_id={entorno.profesional.id}",
        headers=auth,
    )
    assert filtrada.status_code == 200
    franjas = filtrada.json()
    assert len(franjas) == 1
    assert set(franjas[0]) >= {"id", "profesional_id", "dia_semana", "hora_desde", "hora_hasta"}
    assert franjas[0]["dia_semana"] == 0
    completa = client.get("/disponibilidad", headers=auth)
    assert completa.status_code == 200
    assert {f["profesional_id"] for f in completa.json()} == {
        str(entorno.profesional.id),
        str(entorno.segundo.id),
    }


@pytest.mark.parametrize("cual", ["profesional", "prestacion"])
def test_referencia_inexistente_es_404(app: FastAPI, entorno: Entorno, cual: str) -> None:
    datos = params(entorno)
    datos["profesional_id" if cual == "profesional" else "prestacion_id"] = str(uuid.UUID(int=0))
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=datos,
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "RN-AG-01"
    assert respuesta.json()["details"] == {"reason": "no_encontrado"}


def test_prestacion_inactiva_es_422(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, prestacion=entorno.prestacion_inactiva),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["details"] == {"reason": "referencia_inactiva"}


def test_referencias_de_otro_tenant_son_404(app: FastAPI, entorno: Entorno) -> None:
    client = cliente(app)
    auth = cabecera(entorno.recepcion)
    for datos in (
        params(entorno, profesional=entorno.ajeno),
        params(entorno, prestacion=entorno.prestacion_ajena),
    ):
        respuesta = client.get("/disponibilidad/huecos", params=datos, headers=auth)
        assert respuesta.status_code == 404
        assert respuesta.json()["details"] == {"reason": "no_encontrado"}


@pytest.mark.parametrize(
    "desde,hasta",
    [
        (HASTA, DESDE),
        (DESDE, DESDE),
    ],
)
def test_rango_invertido_o_vacio_es_422(
    app: FastAPI, entorno: Entorno, desde: datetime, hasta: datetime
) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, desde=desde, hasta=hasta),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 422


def test_fechas_sin_zona_son_422(app: FastAPI, entorno: Entorno) -> None:
    datos = params(entorno)
    datos["desde"] = "2030-06-03T00:00:00"
    respuesta = cliente(app).get(
        "/disponibilidad/huecos", params=datos, headers=cabecera(entorno.recepcion)
    )
    assert respuesta.status_code == 422


def test_rango_mayor_a_31_dias_es_422(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, hasta=DESDE + timedelta(days=31, seconds=1)),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 422


def test_rango_de_exactamente_31_dias_es_aceptado(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno, hasta=DESDE + timedelta(days=31)),
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200


def test_orden_determinista_y_sin_duplicados(app: FastAPI, entorno: Entorno) -> None:
    client = cliente(app)
    auth = cabecera(entorno.recepcion)
    primero = client.get("/disponibilidad/huecos", params=params(entorno), headers=auth).json()
    segundo = client.get("/disponibilidad/huecos", params=params(entorno), headers=auth).json()
    assert primero == segundo
    inicios = [h["inicio"] for h in primero]
    assert inicios == sorted(inicios)
    assert len(inicios) == len(set(inicios))


def test_openapi_expone_la_subruta_y_no_una_ruta_publica(app: FastAPI) -> None:
    esquema = app.openapi()
    rutas = set(esquema["paths"])
    assert "/disponibilidad/huecos" in rutas
    assert "/turnero" not in rutas
    operacion = esquema["paths"]["/disponibilidad/huecos"]["get"]
    nombres = {parametro["name"] for parametro in operacion["parameters"]}
    assert {"profesional_id", "prestacion_id", "desde", "hasta"} <= nombres


@pytest.mark.parametrize(
    "caso",
    ["sin_jwt", "fuera_de_alcance", "no_encontrado", "rango_invalido"],
)
def test_los_negativos_no_devuelven_huecos_ni_pii(
    app: FastAPI, entorno: Entorno, caso: str
) -> None:
    client = cliente(app)
    if caso == "sin_jwt":
        respuesta = client.get("/disponibilidad/huecos", params=params(entorno))
    elif caso == "fuera_de_alcance":
        respuesta = client.get(
            "/disponibilidad/huecos",
            params=params(entorno, profesional=entorno.segundo),
            headers=cabecera(entorno.usuario),
        )
    elif caso == "no_encontrado":
        datos = params(entorno)
        datos["profesional_id"] = str(uuid.UUID(int=0))
        respuesta = client.get(
            "/disponibilidad/huecos", params=datos, headers=cabecera(entorno.recepcion)
        )
    else:
        respuesta = client.get(
            "/disponibilidad/huecos",
            params=params(entorno, desde=HASTA, hasta=DESDE),
            headers=cabecera(entorno.recepcion),
        )
    assert respuesta.status_code in {401, 403, 404, 422}
    cuerpo = respuesta.text
    assert '"inicio":' not in cuerpo and '"fin":' not in cuerpo
    assert "paciente" not in cuerpo.lower()
    assert "Paciente Ficticio" not in cuerpo and "1145550001" not in cuerpo


def test_profesional_sin_vinculo_es_403(app: FastAPI, entorno: Entorno) -> None:
    respuesta = cliente(app).get(
        "/disponibilidad/huecos",
        params=params(entorno),
        headers=cabecera(entorno.sin_vinculo),
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-03"
    assert respuesta.json()["details"] == {"reason": "profesional_no_vinculado"}
