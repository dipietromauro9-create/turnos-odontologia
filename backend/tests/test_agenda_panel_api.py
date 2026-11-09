"""Agregador de agenda: contrato, rango, RBAC, tenant y minimización de datos."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import EstadoTurno, Paciente, Prestacion, Profesional, Tenant, Turno
from tests.agenda_factories import crear_bloqueo
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_prestacion
from tests.test_agenda_api import cabecera
from tests.test_disponibilidad_service import Entorno
from tests.test_disponibilidad_service import entorno as entorno

pytestmark = pytest.mark.integration

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2030, 6, 3)
DOMINGO = date(2030, 6, 9)
LUNES_SIGUIENTE = date(2030, 6, 10)


@dataclass(frozen=True)
class Sembrado:
    paciente: Paciente
    prestacion: Prestacion
    turno: Turno


@pytest.fixture()
def app(entorno: Entorno) -> FastAPI:
    return app_de_prueba()[0]


def paciente_ficticio(session: Session, tenant: Tenant, **cambios: object) -> Paciente:
    datos = {
        "nombre": "Paciente Ficticio",
        "telefono": "1145550001",
        "documento": "99999999",
        "observaciones": "Dato ficticio de prueba",
    }
    datos.update(cambios)
    fila = Paciente(tenant_id=tenant.id, **datos)
    session.add(fila)
    session.commit()
    return fila


def crear_turno(
    session: Session,
    *,
    tenant: Tenant,
    profesional: Profesional,
    prestacion: Prestacion,
    paciente: Paciente,
    inicio: datetime,
    estado: EstadoTurno = EstadoTurno.RESERVADO,
    **cambios: object,
) -> Turno:
    fila = Turno(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=prestacion.duracion_min),
        estado=estado,
        codigo_publico=uuid.uuid4().hex[:12],
        es_sobreturno=False,
        **cambios,
    )
    session.add(fila)
    session.commit()
    return fila


@pytest.fixture()
def sembrado(entorno: Entorno, session_factory: sessionmaker[Session]) -> Sembrado:
    with session_factory() as session:
        paciente = paciente_ficticio(session, entorno.tenant)
        prestacion = crear_prestacion(session, entorno.tenant, nombre="Consulta Ficticia")
        turno = crear_turno(
            session,
            tenant=entorno.tenant,
            profesional=entorno.profesional,
            prestacion=prestacion,
            paciente=paciente,
            inicio=datetime.combine(LUNES, time(9), TZ),
        )
    return Sembrado(paciente=paciente, prestacion=prestacion, turno=turno)


def test_dia_devuelve_turnos_con_nombres_y_sin_ficha_clinica(
    app: FastAPI, entorno: Entorno, sembrado: Sembrado
) -> None:
    respuesta = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat()},
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["rango"]["desde"].startswith("2030-06-03T00:00:00")
    assert cuerpo["rango"]["hasta"].startswith("2030-06-04T00:00:00")
    assert len(cuerpo["turnos"]) == 1
    turno = cuerpo["turnos"][0]
    assert turno["paciente"] == {
        "id": str(sembrado.paciente.id),
        "nombre": "Paciente Ficticio",
    }
    assert turno["prestacion"]["nombre"] == "Consulta Ficticia"
    assert turno["inicio"].startswith("2030-06-03T09:00:00")
    assert turno["fin"].startswith("2030-06-03T09:30:00")
    assert turno["estado"] == "reservado"
    assert turno["es_sobreturno"] is False
    for prohibido in ("documento", "telefono", "fecha_nac", "observaciones"):
        assert prohibido not in turno
        assert prohibido not in cuerpo["rango"]
    assert "99999999" not in respuesta.text
    assert "1145550001" not in respuesta.text
    assert "Dato ficticio de prueba" not in respuesta.text


def test_semana_normaliza_al_lunes_y_excluye_el_lunes_siguiente(
    app: FastAPI, entorno: Entorno, sembrado: Sembrado, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        prestacion = sembrado.prestacion
        paciente = sembrado.paciente
        crear_turno(
            session,
            tenant=entorno.tenant,
            profesional=entorno.profesional,
            prestacion=prestacion,
            paciente=paciente,
            inicio=datetime.combine(DOMINGO, time(10), TZ),
        )
        crear_turno(
            session,
            tenant=entorno.tenant,
            profesional=entorno.profesional,
            prestacion=prestacion,
            paciente=paciente,
            inicio=datetime.combine(LUNES_SIGUIENTE, time(9), TZ),
        )

    respuesta = cliente(app).get(
        "/agenda/semana",
        params={"desde": DOMINGO.isoformat()},
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["rango"]["desde"].startswith("2030-06-03T00:00:00")
    assert cuerpo["rango"]["hasta"].startswith("2030-06-10T00:00:00")
    inicios = [turno["inicio"][:10] for turno in cuerpo["turnos"]]
    assert inicios == ["2030-06-03", "2030-06-09"]


@pytest.mark.parametrize("fecha", ["2030-13-40", "no-es-fecha"])
def test_fecha_invalida_es_422(app: FastAPI, entorno: Entorno, fecha: str) -> None:
    respuesta = cliente(app).get(
        "/agenda/dia",
        params={"fecha": fecha},
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 422


def test_recepcion_y_dueno_ven_todas_las_agendas(
    app: FastAPI, entorno: Entorno, sembrado: Sembrado, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        crear_turno(
            session,
            tenant=entorno.tenant,
            profesional=entorno.segundo,
            prestacion=sembrado.prestacion,
            paciente=sembrado.paciente,
            inicio=datetime.combine(LUNES, time(11), TZ),
        )

    for usuario in (entorno.recepcion, entorno.dueno):
        respuesta = cliente(app).get(
            "/agenda/dia",
            params={"fecha": LUNES.isoformat()},
            headers=cabecera(usuario),
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert len(cuerpo["turnos"]) == 2
        assert {p["id"] for p in cuerpo["profesionales"]} == {
            str(entorno.profesional.id),
            str(entorno.segundo.id),
        }
        assert str(entorno.ajeno.id) not in {p["id"] for p in cuerpo["profesionales"]}


def test_profesional_sin_flag_solo_ve_su_agenda(
    app: FastAPI, entorno: Entorno, sembrado: Sembrado, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        crear_turno(
            session,
            tenant=entorno.tenant,
            profesional=entorno.segundo,
            prestacion=sembrado.prestacion,
            paciente=sembrado.paciente,
            inicio=datetime.combine(LUNES, time(11), TZ),
        )

    respuesta = cliente(app).get(
        "/agenda/semana",
        params={"desde": LUNES.isoformat()},
        headers=cabecera(entorno.usuario),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert [p["id"] for p in cuerpo["profesionales"]] == [str(entorno.profesional.id)]
    assert {turno["profesional_id"] for turno in cuerpo["turnos"]} == {
        str(entorno.profesional.id)
    }

    ajeno = cliente(app).get(
        "/agenda/semana",
        params={"desde": LUNES.isoformat(), "profesional_id": str(entorno.segundo.id)},
        headers=cabecera(entorno.usuario),
    )
    assert ajeno.status_code == 403
    assert ajeno.json()["code"] == "RN-AU-03"


def test_sin_token_es_401_y_profesional_inexistente_es_404(
    app: FastAPI, entorno: Entorno
) -> None:
    sin_token = cliente(app).get("/agenda/dia", params={"fecha": LUNES.isoformat()})
    assert sin_token.status_code == 401

    inexistente = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat(), "profesional_id": str(uuid.uuid4())},
        headers=cabecera(entorno.recepcion),
    )
    assert inexistente.status_code == 404
    assert inexistente.json()["code"] == "RN-AG-01"


def test_no_mezcla_turnos_de_otro_tenant(
    app: FastAPI,
    entorno: Entorno,
    sembrado: Sembrado,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        prestacion_ajena = crear_prestacion(session, entorno.otro_tenant, nombre="Ajena Ficticia")
        paciente_ajeno = paciente_ficticio(session, entorno.otro_tenant, nombre="Ajeno Ficticio")
        crear_turno(
            session,
            tenant=entorno.otro_tenant,
            profesional=entorno.ajeno,
            prestacion=prestacion_ajena,
            paciente=paciente_ajeno,
            inicio=datetime.combine(LUNES, time(9), TZ),
        )

    respuesta = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat()},
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [turno["id"] for turno in cuerpo["turnos"]] == [str(sembrado.turno.id)]
    assert "Ajeno Ficticio" not in respuesta.text


def test_bloqueos_globales_y_del_profesional(
    app: FastAPI,
    entorno: Entorno,
    sembrado: Sembrado,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        crear_bloqueo(
            session,
            entorno.tenant,
            None,
            desde=datetime(2030, 6, 3, 12, tzinfo=UTC),
            hasta=datetime(2030, 6, 3, 13, tzinfo=UTC),
            motivo="Cierre global ficticio",
        )
        crear_bloqueo(
            session,
            entorno.tenant,
            entorno.profesional,
            desde=datetime(2030, 6, 3, 14, tzinfo=UTC),
            hasta=datetime(2030, 6, 3, 15, tzinfo=UTC),
            motivo="Bloqueo propio ficticio",
        )
        crear_bloqueo(
            session,
            entorno.tenant,
            entorno.segundo,
            desde=datetime(2030, 6, 3, 16, tzinfo=UTC),
            hasta=datetime(2030, 6, 3, 17, tzinfo=UTC),
            motivo="Bloqueo ajeno ficticio",
        )

    recepcion = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat()},
        headers=cabecera(entorno.recepcion),
    ).json()
    assert {b["motivo"] for b in recepcion["bloqueos"]} == {
        "Cierre global ficticio",
        "Bloqueo propio ficticio",
        "Bloqueo ajeno ficticio",
    }

    propio = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat()},
        headers=cabecera(entorno.usuario),
    ).json()
    assert {b["motivo"] for b in propio["bloqueos"]} == {
        "Cierre global ficticio",
        "Bloqueo propio ficticio",
    }


def test_prestaciones_inactivas_no_se_ofrecen(
    app: FastAPI, entorno: Entorno, sembrado: Sembrado, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        crear_prestacion(session, entorno.tenant, nombre="Inactiva Ficticia", activa=False)

    respuesta = cliente(app).get(
        "/agenda/dia",
        params={"fecha": LUNES.isoformat()},
        headers=cabecera(entorno.recepcion),
    )
    assert respuesta.status_code == 200
    nombres = {p["nombre"] for p in respuesta.json()["prestaciones"]}
    assert "Consulta Ficticia" in nombres
    assert "Inactiva Ficticia" not in nombres
