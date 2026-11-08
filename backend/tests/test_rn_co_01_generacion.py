"""Generación programada de recordatorios: ventana, catch-up e idempotencia (RN-CO-01)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import CanalRecordatorio, EstadoRecordatorio, EstadoTurno, Recordatorio
from app.db.session import tenant_session
from app.domain.recordatorios import service
from tests.recordatorios_factories import AHORA, crear_escenario

pytestmark = pytest.mark.integration


def _recordatorios(session_factory: sessionmaker[Session], tenant_id: object) -> list[Recordatorio]:
    with tenant_session(tenant_id) as session:  # type: ignore[arg-type]
        return list(session.query(Recordatorio).all())


def test_turno_confirmado_en_ventana_genera_un_pendiente(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(session, offset_hs=36)

    resultado = service.generar(AHORA)

    assert resultado["creados"] == 1
    filas = _recordatorios(session_factory, escenario.tenant.id)
    assert len(filas) == 1
    fila = filas[0]
    assert fila.turno_id == escenario.turno.id
    assert fila.estado is EstadoRecordatorio.PENDIENTE
    assert fila.canal is CanalRecordatorio.WHATSAPP_MANUAL
    assert fila.enviado_por is None
    assert "Paciente Ficticio" in fila.texto
    assert "Dra. Ficticia" in fila.texto


@pytest.mark.parametrize(
    "estado",
    [EstadoTurno.RESERVADO, EstadoTurno.ATENDIDO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE],
)
def test_turnos_no_confirmados_no_generan(
    app_env: None, session_factory: sessionmaker[Session], estado: EstadoTurno
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(session, estado=estado)

    assert service.generar(AHORA)["creados"] == 0
    assert _recordatorios(session_factory, escenario.tenant.id) == []


def test_turno_mas_alla_de_la_ventana_superior_no_genera(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(session, offset_hs=72)

    assert service.generar(AHORA)["creados"] == 0
    assert _recordatorios(session_factory, escenario.tenant.id) == []


def test_reejecutar_no_duplica(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(session)

    assert service.generar(AHORA)["creados"] == 1
    segundo = service.generar(AHORA + timedelta(minutes=5))
    assert segundo["creados"] == 0
    assert len(_recordatorios(session_factory, escenario.tenant.id)) == 1


def test_recupera_un_turno_proximo_que_quedo_sin_recordatorio(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(
            session, offset_hs=10, creado_en=AHORA - timedelta(hours=30)
        )

    assert service.generar(AHORA)["creados"] == 1
    assert len(_recordatorios(session_factory, escenario.tenant.id)) == 1


def test_no_genera_para_un_turno_de_ultimo_momento(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(
            session, offset_hs=10, creado_en=AHORA - timedelta(hours=2)
        )

    assert service.generar(AHORA)["creados"] == 0
    assert _recordatorios(session_factory, escenario.tenant.id) == []


def test_turno_pasado_no_genera(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        escenario = crear_escenario(
            session, offset_hs=-1, creado_en=AHORA - timedelta(hours=40)
        )

    assert service.generar(AHORA)["creados"] == 0
    assert _recordatorios(session_factory, escenario.tenant.id) == []


def test_la_ventana_se_toma_de_la_configuracion(
    app_env: None, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RECORDATORIO_VENTANA_HS", "12,36")
    from app.core.settings import get_settings

    get_settings.cache_clear()
    try:
        with session_factory() as session:
            dentro = crear_escenario(session, slug="demo", codigo="abcdefgh1234", offset_hs=30)
            fuera = crear_escenario(session, slug="otro", codigo="zyxwvuts5678", offset_hs=40)
        resultado = service.generar(AHORA)
    finally:
        get_settings.cache_clear()

    assert resultado["creados"] == 1
    assert len(_recordatorios(session_factory, dentro.tenant.id)) == 1
    assert _recordatorios(session_factory, fuera.tenant.id) == []


def test_dos_tenants_generan_sus_propios_recordatorios(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        demo = crear_escenario(session, slug="demo", codigo="abcdefgh1234", offset_hs=30)
        otro = crear_escenario(session, slug="otro", codigo="zyxwvuts5678", offset_hs=40)

    assert service.generar(AHORA)["creados"] == 2
    assert len(_recordatorios(session_factory, demo.tenant.id)) == 1
    assert len(_recordatorios(session_factory, otro.tenant.id)) == 1


def test_el_fallo_de_un_tenant_no_revierte_a_los_demas(
    app_env: None, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_factory() as session:
        roto = crear_escenario(
            session, slug="roto", codigo="abcdefgh1234", paciente_nombre="Paciente Error"
        )
        sano = crear_escenario(session, slug="sano", codigo="zyxwvuts5678")

    original = service.texto_recordatorio

    def _falla_para_error(**kwargs: object) -> str:
        if kwargs["paciente"] == "Paciente Error":
            raise RuntimeError("falla ficticia de un tenant")
        return original(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "texto_recordatorio", _falla_para_error)

    resultado = service.generar(AHORA)

    assert resultado["creados"] == 1
    assert _recordatorios(session_factory, roto.tenant.id) == []
    assert len(_recordatorios(session_factory, sano.tenant.id)) == 1


def test_bordes_de_la_ventana(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        en_minimo = crear_escenario(session, slug="min", codigo="abcdefgh1234", offset_hs=24)
        en_maximo = crear_escenario(session, slug="max", codigo="zyxwvuts5678", offset_hs=48)
        justo_afuera = crear_escenario(
            session, slug="fuera", codigo="1234abcdefgh", offset_hs=48.01
        )

    assert service.generar(AHORA)["creados"] == 2
    assert len(_recordatorios(session_factory, en_minimo.tenant.id)) == 1
    assert len(_recordatorios(session_factory, en_maximo.tenant.id)) == 1
    assert _recordatorios(session_factory, justo_afuera.tenant.id) == []


def test_el_job_de_rq_funciona_sin_contexto_http(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    from app.workers.jobs import generar_recordatorios

    with session_factory() as session:
        escenario = crear_escenario(session)

    resultado = generar_recordatorios(AHORA)

    assert resultado["creados"] == 1
    assert len(_recordatorios(session_factory, escenario.tenant.id)) == 1
