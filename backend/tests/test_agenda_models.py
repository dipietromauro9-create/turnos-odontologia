"""Contrato ORM de plantilla semanal y cierres puntuales (C-06)."""

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AuditMixin, Bloqueo, Disponibilidad, TenantMixin
from tests.factories import crear_profesional, crear_tenant

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("modelo", [Disponibilidad, Bloqueo])
def test_agenda_es_tenant_scoped_y_tiene_auditoria(modelo: type) -> None:
    tabla = modelo.__table__
    assert issubclass(modelo, TenantMixin)
    assert issubclass(modelo, AuditMixin)
    assert not tabla.c.tenant_id.nullable
    assert {f.target_fullname for f in tabla.c.tenant_id.foreign_keys} == {"tenant.id"}
    assert {f.target_fullname for f in tabla.c.profesional_id.foreign_keys} == {"profesional.id"}
    for campo in ("creado_en", "actualizado_en"):
        assert isinstance(tabla.c[campo].type, DateTime)
        assert tabla.c[campo].type.timezone


def test_disponibilidad_declara_limites_unicidad_y_orden_de_indice() -> None:
    tabla = Disponibilidad.__table__
    assert not tabla.c.profesional_id.nullable
    assert not tabla.c.hora_desde.type.timezone
    checks = " ".join(str(c.sqltext) for c in tabla.constraints if isinstance(c, CheckConstraint))
    assert "dia_semana BETWEEN 0 AND 6" in checks
    assert "hora_hasta > hora_desde" in checks
    assert any(
        tuple(c.columns.keys())
        == ("tenant_id", "profesional_id", "dia_semana", "hora_desde", "hora_hasta")
        for c in tabla.constraints
        if isinstance(c, UniqueConstraint)
    )
    assert any(
        tuple(i.columns.keys()) == ("tenant_id", "profesional_id", "dia_semana")
        for i in tabla.indexes
    )


def test_bloqueo_admite_cierre_global_y_exige_intervalo_y_motivo() -> None:
    tabla = Bloqueo.__table__
    assert tabla.c.profesional_id.nullable
    assert not tabla.c.motivo.nullable
    assert tabla.c.desde.type.timezone and tabla.c.hasta.type.timezone
    checks = " ".join(str(c.sqltext) for c in tabla.constraints if isinstance(c, CheckConstraint))
    assert "hasta > desde" in checks
    assert "length(trim(motivo)) > 0" in checks
    assert any(
        tuple(i.columns.keys()) == ("tenant_id", "profesional_id", "desde") for i in tabla.indexes
    )


def test_migracion_crea_las_tablas_y_constraints_en_postgres(
    db_engine: Engine, db_url: str
) -> None:
    from alembic import command
    from tests.test_pacientes_model import _alembic_config, _database_url

    config = _alembic_config(db_url)
    try:
        with _database_url(db_url):
            command.downgrade(config, "0005_disponibilidad_bloqueo")
        inspector = inspect(db_engine)
        assert inspector.has_table("disponibilidad")
        assert inspector.has_table("bloqueo")
        assert any(
            c["column_names"]
            == ["tenant_id", "profesional_id", "dia_semana", "hora_desde", "hora_hasta"]
            for c in inspector.get_unique_constraints("disponibilidad")
        )
        with db_engine.connect() as conexion:
            assert conexion.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("0005_disponibilidad_bloqueo")
    finally:
        with _database_url(db_url):
            command.upgrade(config, "head")


@pytest.mark.parametrize("dia", [0, 6, -1, 7])
def test_limites_reales_de_dia(session_factory: sessionmaker[Session], dia: int) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        profesional = crear_profesional(session, tenant)
        session.add(
            Disponibilidad(
                tenant_id=tenant.id,
                profesional_id=profesional.id,
                dia_semana=dia,
                hora_desde=time(9),
                hora_hasta=time(13),
            )
        )
        if dia in (0, 6):
            session.commit()
            assert session.query(Disponibilidad).count() == 1
        else:
            with pytest.raises(IntegrityError):
                session.commit()


@pytest.mark.parametrize("modelo", [Disponibilidad, Bloqueo])
@pytest.mark.parametrize("invalido", ["rango", "fk"])
def test_constraints_de_rango_y_fk(
    session_factory: sessionmaker[Session], modelo: type, invalido: str
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        profesional = crear_profesional(session, tenant)
        profesional_id = uuid.uuid4() if invalido == "fk" else profesional.id
        ahora = datetime(2026, 11, 3, 9, tzinfo=UTC)
        if modelo is Disponibilidad:
            fila = modelo(
                tenant_id=tenant.id,
                profesional_id=profesional_id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(9 if invalido == "rango" else 13),
            )
        else:
            fila = modelo(
                tenant_id=tenant.id,
                profesional_id=profesional_id,
                motivo="Ficticio",
                desde=ahora,
                hasta=ahora if invalido == "rango" else ahora + timedelta(hours=1),
            )
        session.add(fila)
        with pytest.raises(IntegrityError):
            session.commit()


def test_motivo_vacio_es_rechazado_por_la_base(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        ahora = datetime(2026, 11, 3, 9, tzinfo=UTC)
        session.add(
            Bloqueo(tenant_id=tenant.id, desde=ahora, hasta=ahora + timedelta(hours=1), motivo=" ")
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_unicidad_exacta_y_fracciones_independientes(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        primero = crear_profesional(session, tenant)
        segundo = crear_profesional(session, tenant)
        for profesional, dia in ((primero, 0), (primero, 1), (segundo, 0)):
            session.add(
                Disponibilidad(
                    tenant_id=tenant.id,
                    profesional_id=profesional.id,
                    dia_semana=dia,
                    hora_desde=time(9),
                    hora_hasta=time(13),
                )
            )
        session.commit()
        assert session.query(Disponibilidad).count() == 3
        session.add(
            Disponibilidad(
                tenant_id=tenant.id,
                profesional_id=primero.id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(13),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_downgrade_y_upgrade_son_reversibles(db_url: str, db_engine: Engine) -> None:
    from alembic import command
    from tests.test_pacientes_model import _alembic_config, _database_url

    config = _alembic_config(db_url)
    try:
        with _database_url(db_url):
            command.downgrade(config, "0004_paciente")
        assert not inspect(db_engine).has_table("disponibilidad")
        assert not inspect(db_engine).has_table("bloqueo")
        assert inspect(db_engine).has_table("profesional")
    finally:
        with _database_url(db_url):
            command.upgrade(config, "head")
    assert inspect(db_engine).has_table("disponibilidad")
    assert inspect(db_engine).has_table("bloqueo")
