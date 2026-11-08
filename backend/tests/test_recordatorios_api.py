"""Cola de recordatorios, marcado de envío y alcance por rol (RN-CO-03, RN-AU-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
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
    Usuario,
)
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_prestacion, crear_profesional, crear_usuario
from tests.test_agenda_api import cabecera
from tests.test_pacientes_turnos_scope import entorno as entorno

pytestmark = pytest.mark.integration

BASE = datetime(2030, 6, 3, 12, tzinfo=UTC)


@pytest.fixture()
def client(app_env: None, entorno):
    return cliente(app_de_prueba()[0])


def _sembrar(
    session: Session,
    *,
    tenant: Tenant,
    profesional: Profesional,
    paciente: Paciente,
    prestacion: Prestacion,
    codigo: str,
    offset_hs: float = 36,
    estado_turno: EstadoTurno = EstadoTurno.CONFIRMADO,
    estado: EstadoRecordatorio = EstadoRecordatorio.PENDIENTE,
    enviado_por: Usuario | None = None,
    texto: str = "texto viejo",
) -> Recordatorio:
    inicio = BASE + timedelta(hours=offset_hs)
    turno = Turno(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado_turno,
        codigo_publico=codigo,
        es_sobreturno=False,
    )
    session.add(turno)
    session.commit()
    fila = Recordatorio(
        tenant_id=tenant.id,
        turno_id=turno.id,
        canal=CanalRecordatorio.WHATSAPP_MANUAL,
        texto=texto,
        estado=estado,
        enviado_por=enviado_por.id if enviado_por is not None else None,
    )
    session.add(fila)
    session.commit()
    return fila


def _base(entorno) -> dict[str, object]:
    return dict(
        tenant=entorno.base.tenant,
        profesional=entorno.base.profesional,
        paciente=entorno.base.paciente,
        prestacion=entorno.base.prestacion,
    )


def test_sin_jwt_la_cola_es_401(client) -> None:
    assert client.get("/recordatorios/pendientes").status_code == 401


def test_la_cola_incluye_pendientes_y_fallidos_ordenados_y_excluye_el_resto(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        base = _base(entorno)
        pendiente = _sembrar(session, codigo="abcdefgh1234", offset_hs=36, **base)
        fallido = _sembrar(
            session,
            codigo="zyxwvuts5678",
            offset_hs=30,
            estado=EstadoRecordatorio.FALLIDO,
            **base,
        )
        _sembrar(
            session,
            codigo="1234abcdefgh",
            offset_hs=40,
            estado=EstadoRecordatorio.ENVIADO,
            enviado_por=entorno.base.usuario,
            **base,
        )
        _sembrar(
            session,
            codigo="5678zyxwvuts",
            offset_hs=42,
            estado_turno=EstadoTurno.CANCELADO,
            **base,
        )

    respuesta = client.get(
        "/recordatorios/pendientes", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 200, respuesta.text
    filas = respuesta.json()
    assert [fila["id"] for fila in filas] == [str(fallido.id), str(pendiente.id)]
    assert filas[0]["estado"] == "fallido"
    assert filas[1]["estado"] == "pendiente"
    assert filas[1]["paciente"] == "Paciente Ficticio"
    assert filas[1]["profesional"] == "Profesional Ficticio"


def test_el_profesional_sin_dueno_solo_ve_sus_propios_recordatorios(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        propio = _sembrar(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            codigo="abcdefgh1234",
        )
        _sembrar(
            session,
            codigo="zyxwvuts5678",
            offset_hs=40,
            **_base(entorno),
        )

    respuesta = client.get("/recordatorios/pendientes", headers=cabecera(entorno.usuario))

    assert respuesta.status_code == 200
    assert [fila["id"] for fila in respuesta.json()] == [str(propio.id)]


def test_recepcion_ve_el_consolidado(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        recepcion = crear_usuario(
            session, entorno.base.tenant, "recepcion@demo", RolUsuario.RECEPCION
        )
        _sembrar(session, codigo="abcdefgh1234", **_base(entorno))
        _sembrar(
            session,
            tenant=entorno.base.tenant,
            profesional=entorno.profesional,
            paciente=entorno.base.paciente,
            prestacion=entorno.base.prestacion,
            codigo="zyxwvuts5678",
            offset_hs=40,
        )

    respuesta = client.get("/recordatorios/pendientes", headers=cabecera(recepcion))

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 2


def test_marcar_enviado_registra_al_usuario_y_lo_saca_de_la_cola(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fila = _sembrar(session, codigo="abcdefgh1234", **_base(entorno))

    respuesta = client.post(
        f"/recordatorios/{fila.id}/enviado", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "enviado"
    assert cuerpo["enviado_por"] == str(entorno.base.usuario.id)
    assert client.get(
        "/recordatorios/pendientes", headers=cabecera(entorno.base.usuario)
    ).json() == []


def test_reenviar_un_recordatorio_ya_enviado_falla_por_regla(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fila = _sembrar(
            session,
            codigo="abcdefgh1234",
            estado=EstadoRecordatorio.ENVIADO,
            enviado_por=entorno.base.usuario,
            **_base(entorno),
        )

    respuesta = client.post(
        f"/recordatorios/{fila.id}/enviado", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "RN-CO-03"


def test_marcar_fallido_lo_mantiene_en_la_cola_y_sin_responsable(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fila = _sembrar(session, codigo="abcdefgh1234", **_base(entorno))

    respuesta = client.post(
        f"/recordatorios/{fila.id}/fallido", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "fallido"
    assert respuesta.json()["enviado_por"] is None
    cola = client.get("/recordatorios/pendientes", headers=cabecera(entorno.base.usuario))
    assert [item["id"] for item in cola.json()] == [str(fila.id)]


def test_un_fallido_puede_reintentarse_y_marcarse_enviado(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fila = _sembrar(
            session,
            codigo="abcdefgh1234",
            estado=EstadoRecordatorio.FALLIDO,
            **_base(entorno),
        )

    respuesta = client.post(
        f"/recordatorios/{fila.id}/enviado", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "enviado"
    assert respuesta.json()["enviado_por"] == str(entorno.base.usuario.id)


def test_el_texto_de_la_cola_se_renderiza_con_la_fecha_vigente(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fila = _sembrar(session, codigo="abcdefgh1234", **_base(entorno))
        turno = session.get(Turno, fila.turno_id)
        assert turno is not None
        turno.inicio = BASE + timedelta(hours=44)
        turno.fin = turno.inicio + timedelta(minutes=30)
        session.commit()

    filas = client.get(
        "/recordatorios/pendientes", headers=cabecera(entorno.base.usuario)
    ).json()

    assert len(filas) == 1
    assert "texto viejo" not in filas[0]["texto"]
    assert "05/06/2030" in filas[0]["texto"] and "05:00" in filas[0]["texto"]


def test_un_recordatorio_de_otro_tenant_responde_404(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = Tenant(slug="otro", nombre="Consultorio Otro")
        session.add(otro)
        session.commit()
        profesional = crear_profesional(session, otro)
        prestacion = crear_prestacion(session, otro)
        paciente = Paciente(tenant_id=otro.id, nombre="Paciente Otro", telefono="1145559999")
        session.add(paciente)
        session.commit()
        ajeno = _sembrar(
            session,
            tenant=otro,
            profesional=profesional,
            paciente=paciente,
            prestacion=prestacion,
            codigo="abcdefgh1234",
        )

    respuesta = client.post(
        f"/recordatorios/{ajeno.id}/enviado", headers=cabecera(entorno.base.usuario)
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "RN-CO-03"
    with session_factory() as session:
        assert session.get(Recordatorio, ajeno.id).estado is EstadoRecordatorio.PENDIENTE


def test_un_profesional_sin_vinculo_no_accede_a_la_cola(
    client, entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        suelto = crear_usuario(
            session, entorno.base.tenant, "suelto@demo", RolUsuario.PROFESIONAL
        )

    respuesta = client.get("/recordatorios/pendientes", headers=cabecera(suelto))

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-03"
