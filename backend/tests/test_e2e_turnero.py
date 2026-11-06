"""E2E HTTP del turnero público: disponibilidad → reserva → autogestión → liberación."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
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
SLOT_A = datetime.combine(LUNES, time(9, 0), TZ)
SLOT_B = datetime.combine(LUNES, time(9, 30), TZ)
SLOT_C = datetime.combine(LUNES, time(10, 0), TZ)
TELEFONO = "1155551001"


@dataclass(frozen=True)
class EntornoE2E:
    tenant: Tenant
    profesional: Profesional
    prestacion: Prestacion


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[EntornoE2E]:
    with session_factory() as session:
        tenant = crear_tenant(
            session,
            slug=f"e2e-{uuid.uuid4().hex[:8]}",
            nombre="Consultorio E2E",
        )
        profesional = crear_profesional(session, tenant, nombre="Dra. E2E")
        prestacion = crear_prestacion(session, tenant, duracion_min=30)
        crear_disponibilidad(
            session,
            tenant,
            profesional=profesional,
            dia_semana=0,
            hora_desde=time(9, 0),
            hora_hasta=time(13, 0),
        )
        yield EntornoE2E(tenant=tenant, profesional=profesional, prestacion=prestacion)


def _params(entorno: EntornoE2E) -> dict[str, str]:
    return {
        "profesional_id": str(entorno.profesional.id),
        "prestacion_id": str(entorno.prestacion.id),
        "desde": DESDE.isoformat(),
        "hasta": HASTA.isoformat(),
    }


def _reserva(
    entorno: EntornoE2E,
    inicio: datetime,
    *,
    nombre: str = "Paciente E2E",
    telefono: str = TELEFONO,
) -> dict[str, str]:
    return {
        "nombre": nombre,
        "telefono": telefono,
        "profesional_id": str(entorno.profesional.id),
        "prestacion_id": str(entorno.prestacion.id),
        "inicio": inicio.isoformat(),
    }


def _inicios(res: object) -> set[datetime]:
    return {datetime.fromisoformat(h["inicio"]) for h in res.json()}  # type: ignore[index]


def test_e2e_turnero_publico_completo(
    entorno: EntornoE2E, session_factory: sessionmaker[Session]
) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        # 1. Disponibilidad inicial: 8 huecos de 30 min entre 9 y 13.
        disponibilidad = http.get(
            f"/turnero/{entorno.tenant.slug}/disponibilidad",
            params=_params(entorno),
        )
        assert disponibilidad.status_code == 200
        assert len(disponibilidad.json()) == 8

        # 2. Reserva anónima del primer hueco.
        reserva_a = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_reserva(entorno, SLOT_A, nombre="Ana E2E"),
        )
        assert reserva_a.status_code == 201, reserva_a.text
        codigo_a = reserva_a.json()["codigo_publico"]
        assert len(codigo_a) == 12
        assert datetime.fromisoformat(reserva_a.json()["fin"]) == SLOT_A + timedelta(minutes=30)

        # 3. Segundo turno con el mismo teléfono: reutiliza paciente y advierte.
        reserva_b = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_reserva(entorno, SLOT_B, nombre="Ana María E2E"),
        )
        assert reserva_b.status_code == 201, reserva_b.text
        codigo_b = reserva_b.json()["codigo_publico"]
        assert reserva_b.json()["duplicado_advertencia"] is True

        # 4. Consulta por código y reprogramación atómica a SLOT_C.
        consulta = http.get("/turnero/mis-turnos", params={"codigo": codigo_a})
        assert consulta.status_code == 200
        assert consulta.json()["codigo_publico"] == codigo_a

        reprogramada = http.post(
            "/turnero/mis-turnos/reprogramar",
            json={"codigo": codigo_a, "nuevo_inicio": SLOT_C.isoformat()},
        )
        assert reprogramada.status_code == 200, reprogramada.text
        assert reprogramada.json()["codigo_publico"] == codigo_a
        assert datetime.fromisoformat(reprogramada.json()["inicio"]) == SLOT_C

        # 5. Cancelación: libera el hueco y conserva el motivo.
        cancelada = http.post(
            "/turnero/mis-turnos/cancelar",
            json={"codigo": codigo_a, "motivo_cancelacion": "No puedo asistir"},
        )
        assert cancelada.status_code == 200, cancelada.text
        assert cancelada.json()["estado"] == "cancelado"

        final = http.get(
            f"/turnero/{entorno.tenant.slug}/disponibilidad",
            params=_params(entorno),
        )
        inicios = _inicios(final)
        assert SLOT_A in inicios
        assert SLOT_C in inicios
        assert SLOT_B not in inicios

    with session_factory() as session:
        pacientes = list(
            session.execute(select(Paciente).where(Paciente.telefono == TELEFONO)).scalars()
        )
        assert len(pacientes) == 1

        turnos = {
            fila.codigo_publico: fila
            for fila in session.execute(
                select(Turno).where(Turno.tenant_id == entorno.tenant.id)
            ).scalars()
        }
        assert turnos[codigo_a].estado is EstadoTurno.CANCELADO
        assert turnos[codigo_a].motivo_cancelacion == "No puedo asistir"
        assert turnos[codigo_a].inicio == SLOT_C
        assert turnos[codigo_b].estado is EstadoTurno.RESERVADO
        assert turnos[codigo_b].inicio == SLOT_B
