"""Tests de autogestión pública por código (RN-TU-05, RN-TU-06, RN-TU-07)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import EstadoTurno, Paciente, Prestacion, Profesional, Tenant, Turno
from tests.agenda_factories import crear_disponibilidad
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2030, 6, 3)
MARTES = LUNES + timedelta(days=1)
DESDE = datetime.combine(LUNES, time(0), TZ)
HASTA = datetime.combine(MARTES, time(0), TZ)
INICIO_ORIGINAL = datetime.combine(LUNES, time(9, 0), TZ)
INICIO_OCUPADO = datetime.combine(LUNES, time(9, 30), TZ)
INICIO_LIBRE = datetime.combine(LUNES, time(10, 0), TZ)
CODIGO = "ABC123XYZ456"
CODIGO_OCUPADO = "DEF456UVW789"


@dataclass(frozen=True)
class EntornoAutogestion:
    tenant: Tenant
    otro_tenant: Tenant
    profesional: Profesional
    prestacion: Prestacion
    paciente: Paciente
    turno: Turno
    turno_ocupado: Turno


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[EntornoAutogestion]:
    with session_factory() as session:
        tenant = crear_tenant(
            session,
            slug=f"consultorio-{uuid.uuid4().hex[:8]}",
            nombre="Consultorio Autogestión",
        )
        otro_tenant = crear_tenant(session, slug=f"otro-{uuid.uuid4().hex[:8]}")
        profesional = crear_profesional(
            session,
            tenant,
            nombre="Dra. Lucía Ficticia",
            especialidad="Ortodoncia",
            activo=True,
        )
        prestacion = crear_prestacion(
            session,
            tenant,
            nombre="Consulta Ficticia",
            duracion_min=30,
            precio_ref=15000.0,
        )
        crear_disponibilidad(
            session,
            tenant,
            profesional=profesional,
            dia_semana=0,
            hora_desde=time(9, 0),
            hora_hasta=time(11, 0),
        )
        paciente = Paciente(
            tenant_id=tenant.id,
            nombre="Paciente Ficticio",
            telefono="1144445555",
        )
        session.add(paciente)
        session.flush()

        turno = Turno(
            tenant_id=tenant.id,
            profesional_id=profesional.id,
            prestacion_id=prestacion.id,
            paciente_id=paciente.id,
            inicio=INICIO_ORIGINAL,
            fin=INICIO_ORIGINAL + timedelta(minutes=30),
            estado=EstadoTurno.RESERVADO,
            codigo_publico=CODIGO,
            es_sobreturno=False,
        )
        turno_ocupado = Turno(
            tenant_id=tenant.id,
            profesional_id=profesional.id,
            prestacion_id=prestacion.id,
            paciente_id=paciente.id,
            inicio=INICIO_OCUPADO,
            fin=INICIO_OCUPADO + timedelta(minutes=30),
            estado=EstadoTurno.RESERVADO,
            codigo_publico=CODIGO_OCUPADO,
            es_sobreturno=False,
        )
        session.add_all([turno, turno_ocupado])
        session.commit()

        yield EntornoAutogestion(
            tenant=tenant,
            otro_tenant=otro_tenant,
            profesional=profesional,
            prestacion=prestacion,
            paciente=paciente,
            turno=turno,
            turno_ocupado=turno_ocupado,
        )


def _consultar(entorno: EntornoAutogestion, codigo: str = CODIGO):
    app, _ = app_de_prueba()
    with cliente(app) as http:
        return http.get("/turnero/mis-turnos", params={"codigo": codigo})


def _cancelar(
    entorno: EntornoAutogestion,
    codigo: str = CODIGO,
    motivo: str | None = "No puedo asistir",
):
    app, _ = app_de_prueba()
    with cliente(app) as http:
        return http.post(
            "/turnero/mis-turnos/cancelar",
            json={"codigo": codigo, "motivo_cancelacion": motivo},
        )


def _reprogramar(
    entorno: EntornoAutogestion,
    nuevo_inicio: datetime,
    codigo: str = CODIGO,
):
    app, _ = app_de_prueba()
    with cliente(app) as http:
        return http.post(
            "/turnero/mis-turnos/reprogramar",
            json={"codigo": codigo, "nuevo_inicio": nuevo_inicio.isoformat()},
        )


def test_mis_turnos_codigo_valido_devuelve_detalle_sin_pii(
    entorno: EntornoAutogestion,
) -> None:
    res = _consultar(entorno)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["codigo_publico"] == CODIGO
    assert data["estado"] == "reservado"
    assert data["profesional"]["nombre"] == "Dra. Lucía Ficticia"
    assert data["prestacion"]["nombre"] == "Consulta Ficticia"
    assert "paciente" not in data
    assert "telefono" not in data
    assert "1144445555" not in res.text


@pytest.mark.parametrize("codigo", ["NOEXISTE123", "abc", "x" * 64])
def test_mis_turnos_codigo_invalido_404_generico(
    entorno: EntornoAutogestion, codigo: str
) -> None:
    res = _consultar(entorno, codigo)
    assert res.status_code == 404
    assert res.json()["code"] == "RN-TU-06"
    assert res.json()["details"]["reason"] == "codigo_invalido"


def test_cancelar_guarda_motivo_y_libera_hueco(
    entorno: EntornoAutogestion, session_factory: sessionmaker[Session]
) -> None:
    res = _cancelar(entorno)
    assert res.status_code == 200, res.text
    assert res.json()["estado"] == "cancelado"

    with session_factory() as session:
        fila = session.get(Turno, entorno.turno.id)
    assert fila is not None
    assert fila.estado is EstadoTurno.CANCELADO
    assert fila.motivo_cancelacion == "No puedo asistir"

    app, _ = app_de_prueba()
    with cliente(app) as http:
        huecos = http.get(
            f"/turnero/{entorno.tenant.slug}/disponibilidad",
            params={
                "profesional_id": str(entorno.profesional.id),
                "prestacion_id": str(entorno.prestacion.id),
                "desde": DESDE.isoformat(),
                "hasta": HASTA.isoformat(),
            },
        )
    assert huecos.status_code == 200
    inicios = {datetime.fromisoformat(h["inicio"]) for h in huecos.json()}
    assert INICIO_ORIGINAL in inicios


def test_cancelar_turno_ya_cancelado_422(
    entorno: EntornoAutogestion,
) -> None:
    assert _cancelar(entorno).status_code == 200
    repetido = _cancelar(entorno)
    assert repetido.status_code == 422
    assert repetido.json()["code"] == "RN-TU-04"


def test_reprogramar_exitoso_conserva_codigo_y_estado(
    entorno: EntornoAutogestion, session_factory: sessionmaker[Session]
) -> None:
    res = _reprogramar(entorno, INICIO_LIBRE)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["codigo_publico"] == CODIGO
    assert data["estado"] == "reservado"
    assert datetime.fromisoformat(data["inicio"]) == INICIO_LIBRE
    assert datetime.fromisoformat(data["fin"]) == INICIO_LIBRE + timedelta(minutes=30)

    with session_factory() as session:
        fila = session.get(Turno, entorno.turno.id)
    assert fila is not None
    assert fila.codigo_publico == CODIGO
    assert fila.inicio == INICIO_LIBRE


def test_reprogramar_a_horario_ocupado_409_mantiene_original(
    entorno: EntornoAutogestion, session_factory: sessionmaker[Session]
) -> None:
    res = _reprogramar(entorno, INICIO_OCUPADO)
    assert res.status_code == 409
    assert res.json()["code"] == "RN-TU-01"

    with session_factory() as session:
        fila = session.get(Turno, entorno.turno.id)
    assert fila is not None
    assert fila.inicio == INICIO_ORIGINAL
    assert fila.fin == INICIO_ORIGINAL + timedelta(minutes=30)


def test_reprogramar_turno_cancelado_422(
    entorno: EntornoAutogestion,
) -> None:
    assert _cancelar(entorno).status_code == 200
    res = _reprogramar(entorno, INICIO_LIBRE)
    assert res.status_code == 422
    assert res.json()["code"] == "RN-TU-04"
