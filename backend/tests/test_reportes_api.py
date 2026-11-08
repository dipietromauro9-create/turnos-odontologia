"""Reportes de ocupación, ausencias e IN-03: fórmulas, RBAC y alcance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Bloqueo,
    CanalRecordatorio,
    EstadoRecordatorio,
    EstadoTurno,
    Paciente,
    Prestacion,
    Profesional,
    Recordatorio,
    RolUsuario,
    Tenant,
    Turno,
)
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_prestacion, crear_profesional, crear_usuario
from tests.test_agenda_api import cabecera
from tests.test_pacientes_turnos_scope import entorno as entorno
from tests.turnos_factories import INICIO

pytestmark = pytest.mark.integration

DESDE = datetime(2030, 6, 3, 0, 0, tzinfo=UTC)
HASTA = datetime(2030, 6, 4, 0, 0, tzinfo=UTC)
CONSULTA = {
    "desde": DESDE.isoformat(),
    "hasta": HASTA.isoformat(),
}


@pytest.fixture()
def client(app_env: None, entorno):
    return cliente(app_de_prueba()[0])


def _turno(
    session: Session,
    *,
    tenant: Tenant,
    profesional: Profesional,
    paciente: Paciente,
    prestacion: Prestacion,
    hora: int,
    minutos: int = 30,
    estado: EstadoTurno = EstadoTurno.CONFIRMADO,
    codigo: str = "abcdefgh1234",
) -> Turno:
    inicio = INICIO.replace(hour=hora)
    turno = Turno(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=minutos),
        estado=estado,
        codigo_publico=codigo,
        es_sobreturno=False,
    )
    session.add(turno)
    session.commit()
    return turno


def _params(**cambios: object) -> dict[str, str]:
    datos = dict(CONSULTA)
    datos.update({clave: str(valor) for clave, valor in cambios.items()})
    return datos


def test_diseno_sin_jwt_es_401(client) -> None:
    assert client.get("/reportes/ocupacion", params=CONSULTA).status_code == 401


def test_el_dueno_ve_el_consolidado_con_ocupacion_por_minutos(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        _turno(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.base.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            hora=9,
            codigo="abcdefgh1234",
        )
        _turno(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.base.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            hora=10,
            estado=EstadoTurno.ATENDIDO,
            codigo="zyxwvuts5678",
        )
        _turno(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            hora=9,
            codigo="1234abcdefgh",
        )

    respuesta = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 200, respuesta.text
    filas = {fila["profesional_id"]: fila for fila in respuesta.json()}
    assert len(filas) == 2
    propia = filas[str(entorno.base.profesional.id)]
    assert propia["turnos_activos"] == 2
    assert propia["minutos_disponibles"] == 240
    assert propia["minutos_ocupados"] == 60
    assert propia["ocupacion"] == pytest.approx(0.25)
    otra = filas[str(entorno.profesional.id)]
    assert otra["minutos_ocupados"] == 30
    assert otra["ocupacion"] == pytest.approx(0.125)


def test_un_bloqueo_reduce_los_minutos_disponibles(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        session.add(
            Bloqueo(
                tenant_id=entorno.base.tenant.id,
                profesional_id=entorno.base.profesional.id,
                desde=INICIO.replace(hour=10),
                hasta=INICIO.replace(hour=11),
                motivo="Cierre ficticio",
            )
        )
        session.commit()

    filas = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    ).json()
    propia = next(f for f in filas if f["profesional_id"] == str(entorno.base.profesional.id))
    assert propia["minutos_disponibles"] == 180


def test_el_profesional_sin_dueno_solo_ve_lo_propio(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        _turno(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.base.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            hora=9,
            codigo="abcdefgh1234",
        )

    respuesta = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(entorno.usuario)
    )

    assert respuesta.status_code == 200
    assert [fila["profesional_id"] for fila in respuesta.json()] == [
        str(entorno.profesional.id)
    ]


def test_pedir_otro_profesional_sin_dueno_es_403(
    client, entorno
) -> None:
    respuesta = client.get(
        "/reportes/ocupacion",
        params=_params(profesional_id=entorno.base.profesional.id),
        headers=cabecera(entorno.usuario),
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-03"


def test_la_recepcion_no_accede_a_reportes(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        recepcion = crear_usuario(
            session, entorno.base.tenant, "recepcion@demo", RolUsuario.RECEPCION
        )

    respuesta = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(recepcion)
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_rango_invertido_es_422(client, entorno) -> None:
    respuesta = client.get(
        "/reportes/ocupacion",
        params={"desde": HASTA.isoformat(), "hasta": DESDE.isoformat()},
        headers=cabecera(entorno.base.usuario),
    )
    assert respuesta.status_code == 422


def test_rango_demasiado_largo_es_422(client, entorno) -> None:
    respuesta = client.get(
        "/reportes/ocupacion",
        params={"desde": DESDE.isoformat(), "hasta": (DESDE + timedelta(days=367)).isoformat()},
        headers=cabecera(entorno.base.usuario),
    )
    assert respuesta.status_code == 422


def test_periodo_sin_datos_devuelve_ceros(
    client, entorno
) -> None:
    filas = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    ).json()
    assert len(filas) == 2
    assert all(fila["turnos_activos"] == 0 and fila["ocupacion"] == 0 for fila in filas)


def test_tasa_de_ausencia(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        for hora, estado, codigo in (
            (9, EstadoTurno.ATENDIDO, "abcdefgh1234"),
            (10, EstadoTurno.ATENDIDO, "zyxwvuts5678"),
            (11, EstadoTurno.AUSENTE, "1234abcdefgh"),
        ):
            _turno(
                session,
                tenant=entorno.base.tenant,
                profesional=entorno.base.profesional,
                paciente=entorno.base.paciente,
                prestacion=entorno.base.prestacion,
                hora=hora,
                estado=estado,
                codigo=codigo,
            )

    filas = client.get(
        "/reportes/ausencias", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    ).json()
    propia = next(f for f in filas if f["profesional_id"] == str(entorno.base.profesional.id))
    assert propia["atendidos"] == 2 and propia["ausentes"] == 1
    assert propia["tasa_ausencia"] == pytest.approx(1 / 3)


def test_ratio_in_03(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        turno = _turno(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.base.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            hora=9,
            codigo="abcdefgh1234",
        )
        session.add(
            Recordatorio(
                tenant_id=entorno.base.tenant.id,
                turno_id=turno.id,
                canal=CanalRecordatorio.WHATSAPP_MANUAL,
                texto="Recordatorio ficticio",
                estado=EstadoRecordatorio.ENVIADO,
                enviado_por=entorno.base.usuario.id,
            )
        )
        session.commit()

    filas = client.get(
        "/reportes/recordatorios", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    ).json()
    propia = next(f for f in filas if f["profesional_id"] == str(entorno.base.profesional.id))
    assert propia["turnos_confirmados"] == 1
    assert propia["recordatorios_enviados"] == 1
    assert propia["ratio"] == 1.0


def test_un_profesional_de_otro_tenant_no_es_visible(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = Tenant(slug="otro", nombre="Consultorio Otro")
        session.add(otro)
        session.commit()
        ajeno = crear_profesional(session, otro)
        crear_prestacion(session, otro)

    respuesta = client.get(
        "/reportes/ocupacion",
        params=_params(profesional_id=ajeno.id),
        headers=cabecera(entorno.base.usuario),
    )
    assert respuesta.status_code == 404


def test_fechas_sin_zona_horaria_son_422(client, entorno) -> None:
    respuesta = client.get(
        "/reportes/ocupacion",
        params={"desde": "2030-06-03T00:00:00", "hasta": "2030-06-04T00:00:00"},
        headers=cabecera(entorno.base.usuario),
    )
    assert respuesta.status_code == 422


def test_un_profesional_inactivo_no_aparece_en_el_consolidado(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        crear_profesional(
            session,
            entorno.base.tenant,
            nombre="Profesional Inactivo",
            activo=False,
        )

    filas = client.get(
        "/reportes/ocupacion", params=CONSULTA, headers=cabecera(entorno.base.usuario)
    ).json()
    assert all(fila["nombre"] != "Profesional Inactivo" for fila in filas)
