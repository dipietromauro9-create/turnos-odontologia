"""Tests para endpoints públicos de catálogo y disponibilidad del turnero."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
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


@dataclass(frozen=True)
class EntornoTurnero:
    tenant: Tenant
    otro_tenant: Tenant
    profesional: Profesional
    profesional_inactivo: Profesional
    prestacion: Prestacion
    prestacion_inactiva: Prestacion
    paciente: Paciente
    turno: Turno


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[EntornoTurnero]:
    with session_factory() as session:
        slug = f"consultorio-{uuid.uuid4().hex[:8]}"
        tenant = crear_tenant(session, slug=slug, nombre="Consultorio Sonrisas")
        otro_tenant = crear_tenant(session, slug=f"otro-{uuid.uuid4().hex[:8]}")

        profesional = crear_profesional(
            session,
            tenant,
            nombre="Dra. Martina Pérez",
            especialidad="Ortodoncia",
            activo=True,
        )
        profesional_inactivo = crear_profesional(
            session,
            tenant,
            nombre="Dr. Inactivo",
            activo=False,
        )
        prestacion = crear_prestacion(
            session,
            tenant,
            nombre="Consulta Ortodoncia",
            duracion_min=30,
            precio_ref=12000.0,
            activa=True,
        )
        prestacion_inactiva = crear_prestacion(
            session,
            tenant,
            nombre="Blanqueamiento Desactivado",
            activa=False,
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
            nombre="Paciente Secreto",
            telefono="1144445555",
        )
        session.add(paciente)
        session.flush()

        inicio_ocupado = datetime.combine(LUNES, time(9, 0), TZ)
        fin_ocupado = datetime.combine(LUNES, time(9, 30), TZ)
        turno = Turno(
            tenant_id=tenant.id,
            profesional_id=profesional.id,
            prestacion_id=prestacion.id,
            paciente_id=paciente.id,
            inicio=inicio_ocupado,
            fin=fin_ocupado,
            estado=EstadoTurno.RESERVADO,
            codigo_publico="ABC123XYZ456",
            es_sobreturno=False,
        )
        session.add(turno)
        session.commit()

        yield EntornoTurnero(
            tenant=tenant,
            otro_tenant=otro_tenant,
            profesional=profesional,
            profesional_inactivo=profesional_inactivo,
            prestacion=prestacion,
            prestacion_inactiva=prestacion_inactiva,
            paciente=paciente,
            turno=turno,
        )


def test_catalogo_publico_slug_inexistente_404(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.get("/turnero/slug-inexistente-xyz/catalogo")
        assert res.status_code == 404
        assert res.json().get("code") in {"404", "RN-AG-01", "TENANT_NO_ENCONTRADO"}


def test_catalogo_publico_devuelve_profesionales_y_prestaciones_activas(
    entorno: EntornoTurnero,
) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.get(f"/turnero/{entorno.tenant.slug}/catalogo")
        assert res.status_code == 200
        data = res.json()

        assert data["consultorio"]["slug"] == entorno.tenant.slug
        assert data["consultorio"]["nombre"] == entorno.tenant.nombre

        nombres_prof = [p["nombre"] for p in data["profesionales"]]
        assert "Dra. Martina Pérez" in nombres_prof
        assert "Dr. Inactivo" not in nombres_prof

        nombres_prest = [pr["nombre"] for pr in data["prestaciones"]]
        assert "Consulta Ortodoncia" in nombres_prest
        assert "Blanqueamiento Desactivado" not in nombres_prest


def test_disponibilidad_publica_sin_jwt_devuelve_huecos(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": HASTA.isoformat(),
        }
        res = http.get(f"/turnero/{entorno.tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 200
        huecos = res.json()
        assert isinstance(huecos, list)
        # De 9:00 a 11:00 con el turno de 9:00 a 9:30 ocupado quedan 3 huecos.
        assert len(huecos) == 3
        claves = {"inicio", "fin", "profesional_id", "prestacion_id"}
        assert all(set(h.keys()) == claves for h in huecos)


def test_disponibilidad_publica_sin_pii(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": HASTA.isoformat(),
        }
        res = http.get(f"/turnero/{entorno.tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 200
        contenido = res.text
        assert "Paciente Secreto" not in contenido
        assert "1144445555" not in contenido
        assert "paciente@secreto.com" not in contenido


def test_disponibilidad_publica_slug_inexistente_404(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": HASTA.isoformat(),
        }
        res = http.get("/turnero/slug-ficticio-inexistente/disponibilidad", params=params)
        assert res.status_code == 404


def test_disponibilidad_rango_mayor_a_31_dias_devuelve_422(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": (DESDE + timedelta(days=32)).isoformat(),
        }
        res = http.get(f"/turnero/{entorno.tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 422


def test_disponibilidad_rango_invertido_devuelve_422(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": HASTA.isoformat(),
            "hasta": DESDE.isoformat(),
        }
        res = http.get(f"/turnero/{entorno.tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 422


def test_disponibilidad_profesional_inactivo_devuelve_422(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional_inactivo.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": HASTA.isoformat(),
        }
        res = http.get(f"/turnero/{entorno.tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 422


def test_disponibilidad_profesional_de_otro_tenant_devuelve_404(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        params = {
            "profesional_id": str(entorno.profesional.id),
            "prestacion_id": str(entorno.prestacion.id),
            "desde": DESDE.isoformat(),
            "hasta": HASTA.isoformat(),
        }
        # Consultamos el slug de otro tenant con el profesional del tenant A
        res = http.get(f"/turnero/{entorno.otro_tenant.slug}/disponibilidad", params=params)
        assert res.status_code == 404


def test_aislamiento_catalogo_entre_tenants(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.get(f"/turnero/{entorno.otro_tenant.slug}/catalogo")
        assert res.status_code == 200
        data = res.json()
        assert data["consultorio"]["slug"] == entorno.otro_tenant.slug
        # En otro_tenant no se crearon profesionales ni prestaciones
        assert len(data["profesionales"]) == 0
        assert len(data["prestaciones"]) == 0


# --- Sección 3: reserva pública anónima + rate limiting ---------------------

LIBRE = datetime.combine(LUNES, time(9, 30), TZ)
OTRO_LIBRE = datetime.combine(LUNES, time(10, 0), TZ)


def _payload_reserva(
    entorno: EntornoTurnero,
    *,
    inicio: datetime = LIBRE,
    nombre: str = "Paciente Turnero",
    telefono: str = "1155550001",
) -> dict[str, str]:
    return {
        "nombre": nombre,
        "telefono": telefono,
        "profesional_id": str(entorno.profesional.id),
        "prestacion_id": str(entorno.prestacion.id),
        "inicio": inicio.isoformat(),
    }


def _pacientes_por_telefono(
    session_factory: sessionmaker[Session], telefono: str
) -> list[Paciente]:
    with session_factory() as session:
        return list(
            session.execute(
                select(Paciente).where(Paciente.telefono == telefono)
            ).scalars()
        )


def test_reserva_publica_exitosa_devuelve_codigo_y_fin_calculado(
    entorno: EntornoTurnero, session_factory: sessionmaker[Session]
) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_payload_reserva(entorno, telefono="1155550001"),
        )
    assert res.status_code == 201, res.text
    data = res.json()
    assert len(data["codigo_publico"]) == 12
    assert data["estado"] == "reservado"
    assert data["duplicado_advertencia"] is False
    assert datetime.fromisoformat(data["fin"]) == datetime.combine(LUNES, time(10, 0), TZ)

    creados = _pacientes_por_telefono(session_factory, "1155550001")
    assert len(creados) == 1
    assert creados[0].tenant_id == entorno.tenant.id


def test_reserva_publica_reutiliza_paciente_y_advierte_nombre_distinto(
    entorno: EntornoTurnero, session_factory: sessionmaker[Session]
) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        primero = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_payload_reserva(entorno, nombre="Ana Ficticia", telefono="1155550002"),
        )
        segundo = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_payload_reserva(
                entorno,
                inicio=OTRO_LIBRE,
                nombre="Ana María Ficticia",
                telefono="11 5555 0002",
            ),
        )
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["duplicado_advertencia"] is True
    assert len(_pacientes_por_telefono(session_factory, "1155550002")) == 1


def test_reserva_publica_hueco_ocupado_409(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_payload_reserva(
                entorno,
                inicio=datetime.combine(LUNES, time(9, 0), TZ),
                telefono="1155550003",
            ),
        )
    assert res.status_code == 409
    assert res.json()["code"] == "RN-TU-01"


def test_reserva_publica_fuera_de_disponibilidad_422(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.post(
            f"/turnero/{entorno.tenant.slug}/reservas",
            json=_payload_reserva(
                entorno,
                inicio=datetime.combine(LUNES, time(12, 0), TZ),
                telefono="1155550004",
            ),
        )
    assert res.status_code == 422
    assert res.json()["code"] == "RN-AG-01"


@pytest.mark.parametrize(
    "cambio",
    [
        {"telefono": "123"},
        {"nombre": "   "},
    ],
)
def test_reserva_publica_datos_invalidos_422(
    entorno: EntornoTurnero, cambio: dict[str, str]
) -> None:
    app, _ = app_de_prueba()
    payload = {**_payload_reserva(entorno, telefono="1155550005"), **cambio}
    with cliente(app) as http:
        res = http.post(f"/turnero/{entorno.tenant.slug}/reservas", json=payload)
    assert res.status_code == 422


def test_reserva_publica_slug_inexistente_404(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        res = http.post(
            "/turnero/slug-inexistente-xyz/reservas",
            json=_payload_reserva(entorno, telefono="1155550006"),
        )
    assert res.status_code == 404


def test_rate_limit_publico_429(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()
    with cliente(app) as http:
        for _ in range(10):
            assert http.get(f"/turnero/{entorno.tenant.slug}/catalogo").status_code == 200
        excedido = http.get(f"/turnero/{entorno.tenant.slug}/catalogo")
    assert excedido.status_code == 429
    assert excedido.headers["Retry-After"]
    assert excedido.json()["code"] == "RN-GL-01"


def test_reserva_publica_concurrente_solo_uno_gana(entorno: EntornoTurnero) -> None:
    app, _ = app_de_prueba()

    def reservar(telefono: str) -> int:
        with cliente(app) as http:
            res = http.post(
                f"/turnero/{entorno.tenant.slug}/reservas",
                json=_payload_reserva(entorno, telefono=telefono),
            )
        return res.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = sorted(pool.map(reservar, ["1155550007", "1155550008"]))

    assert estados == [201, 409]
