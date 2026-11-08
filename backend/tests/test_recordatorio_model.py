"""Modelo `Recordatorio` y migración `0007_recordatorio`: unicidad, coherencia y frontera."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import DateTime, Index, UniqueConstraint, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AuditMixin,
    CanalRecordatorio,
    EstadoRecordatorio,
    EstadoTurno,
    Paciente,
    Recordatorio,
    TenantMixin,
    Turno,
)
from app.db.session import tenant_session
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration


def _turno(session: Session, slug: str = "demo", codigo: str = "abcdefgh1234") -> Turno:
    tenant = crear_tenant(session, slug)
    profesional = crear_profesional(session, tenant)
    prestacion = crear_prestacion(session, tenant)
    paciente = Paciente(tenant_id=tenant.id, nombre="Paciente Ficticio", telefono="1145550001")
    session.add(paciente)
    session.commit()
    inicio = datetime(2030, 6, 3, 12, tzinfo=UTC)
    turno = Turno(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=EstadoTurno.CONFIRMADO,
        codigo_publico=codigo,
        es_sobreturno=False,
    )
    session.add(turno)
    session.commit()
    return turno


def _fila(turno: Turno, **cambios: object) -> Recordatorio:
    datos: dict[str, object] = {
        "tenant_id": turno.tenant_id,
        "turno_id": turno.id,
        "canal": CanalRecordatorio.WHATSAPP_MANUAL,
        "texto": "Recordatorio ficticio",
        "estado": EstadoRecordatorio.PENDIENTE,
    }
    datos.update(cambios)
    return Recordatorio(**datos)


def test_recordatorio_metadata_frontera_referencias_y_unicidad() -> None:
    tabla = Recordatorio.__table__
    assert issubclass(Recordatorio, TenantMixin) and issubclass(Recordatorio, AuditMixin)
    assert not tabla.c.tenant_id.nullable

    fk_turno = next(iter(tabla.c.turno_id.foreign_keys))
    assert fk_turno.target_fullname == "turno.id" and fk_turno.ondelete == "CASCADE"
    fk_usuario = next(iter(tabla.c.enviado_por.foreign_keys))
    assert fk_usuario.target_fullname == "usuario.id" and fk_usuario.ondelete == "SET NULL"

    assert any(
        isinstance(c, UniqueConstraint) and tuple(c.columns.keys()) == ("tenant_id", "turno_id")
        for c in tabla.constraints
    )
    assert any(
        isinstance(i, Index) and tuple(i.columns.keys()) == ("tenant_id", "estado")
        for i in tabla.indexes
    )
    for campo in ("creado_en", "actualizado_en"):
        assert isinstance(tabla.c[campo].type, DateTime) and tabla.c[campo].type.timezone


def test_migracion_crea_tabla_enums_y_constraints(db_engine: Engine) -> None:
    assert inspect(db_engine).has_table("recordatorio")
    with db_engine.connect() as conn:
        etiquetas = {
            fila[0]: fila[1]
            for fila in conn.execute(
                text(
                    "SELECT t.typname, e.enumlabel FROM pg_type t "
                    "JOIN pg_enum e ON e.enumtypid = t.oid "
                    "WHERE t.typname IN ('canal_recordatorio', 'estado_recordatorio')"
                )
            )
        }
        assert etiquetas["canal_recordatorio"] == "whatsapp_manual"
        definicion = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_recordatorio_enviado_por_coherente'"
            )
        ).scalar_one()
    assert "enviado" in definicion and "enviado_por" in definicion


def test_un_segundo_recordatorio_para_el_mismo_turno_se_rechaza(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        turno = _turno(session)
        session.add(_fila(turno))
        session.commit()
        session.add(_fila(turno))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "uq_recordatorio_turno"


def test_enviado_sin_enviado_por_viola_el_check(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        turno = _turno(session)
        session.add(_fila(turno, estado=EstadoRecordatorio.ENVIADO))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "ck_recordatorio_enviado_por_coherente"


def test_borrado_del_turno_arrastra_sus_recordatorios(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        turno = _turno(session)
        session.add(_fila(turno))
        session.commit()
        session.execute(text("DELETE FROM turno WHERE id = :id"), {"id": turno.id})
        session.commit()
        assert session.execute(text("SELECT count(*) FROM recordatorio")).scalar_one() == 0


def test_lectura_queda_aislada_por_tenant(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        turno_demo = _turno(session, "demo", "abcdefgh1234")
        turno_otro = _turno(session, "otro", "zyxwvuts5678")
        session.add(_fila(turno_demo))
        session.add(_fila(turno_otro))
        session.commit()
        demo_id = turno_demo.tenant_id

    with tenant_session(demo_id) as session:
        filas = session.query(Recordatorio).all()
        assert len(filas) == 1
        assert filas[0].tenant_id == demo_id


def test_escritura_de_otro_tenant_se_rechaza(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    from app.db.session import TenantIsolationError

    with session_factory() as session:
        turno_demo = _turno(session, "demo", "abcdefgh1234")
        turno_otro = _turno(session, "otro", "zyxwvuts5678")
        demo_id = turno_demo.tenant_id
        fila_ajena = _fila(turno_otro)

    with tenant_session(demo_id) as session:
        session.add(fila_ajena)
        with pytest.raises(TenantIsolationError):
            session.flush()
