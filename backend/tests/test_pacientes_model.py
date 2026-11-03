"""Modelo `Paciente` y migración `0004_paciente`: frontera, índices y borrado físico."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AuditMixin,
    Paciente,
    Tenant,
    TenantMixin,
    Usuario,
)
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[1]

COLUMNAS_DE_BORRADO_LOGICO = {"deleted_at", "eliminado_en", "activo"}


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@contextmanager
def _database_url(url: str) -> Iterator[None]:
    """`alembic/env.py` prioriza `DATABASE_URL`; apuntarlo a la base de test."""
    previo = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        yield
    finally:
        if previo is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previo


def _indices(tabla: object) -> dict[str, tuple[str, ...]]:
    from sqlalchemy import Table

    assert isinstance(tabla, Table)
    return {
        indice.name: tuple(columna.name for columna in indice.columns) for indice in tabla.indexes
    }


def test_paciente_declara_frontera_de_tenant_y_auditoria() -> None:
    tabla = Paciente.__table__

    assert issubclass(Paciente, TenantMixin)
    assert issubclass(Paciente, AuditMixin)
    assert tabla.name == "paciente"
    assert tabla.primary_key.name == "pk_paciente"

    assert isinstance(tabla.c.id.type, Uuid)
    assert tabla.c.id.server_default is not None

    tenant_id = tabla.c.tenant_id
    assert isinstance(tenant_id.type, Uuid)
    assert tenant_id.nullable is False
    fks_tenant = list(tenant_id.foreign_keys)
    assert len(fks_tenant) == 1
    assert fks_tenant[0].column is Tenant.__table__.c.id
    assert fks_tenant[0].constraint.name == "fk_paciente_tenant_id_tenant"


def test_paciente_tiene_ficha_basica_con_campos_opcionales() -> None:
    tabla = Paciente.__table__

    assert isinstance(tabla.c.nombre.type, String)
    assert tabla.c.nombre.nullable is False
    assert isinstance(tabla.c.telefono.type, String)
    assert tabla.c.telefono.nullable is False

    assert tabla.c.documento.nullable is True
    assert isinstance(tabla.c.fecha_nac.type, Date)
    assert tabla.c.fecha_nac.nullable is True
    assert tabla.c.observaciones.nullable is True


def test_paciente_vincula_usuario_creador_opcionalmente() -> None:
    creado_por = Paciente.__table__.c.creado_por_usuario_id

    assert isinstance(creado_por.type, Uuid)
    assert creado_por.nullable is True
    fks = list(creado_por.foreign_keys)
    assert len(fks) == 1
    assert isinstance(fks[0], ForeignKey)
    assert fks[0].column is Usuario.__table__.c.id
    assert fks[0].constraint.name == "fk_paciente_creado_por_usuario_id_usuario"
    assert fks[0].ondelete == "SET NULL"


def test_paciente_no_tiene_columnas_de_borrado_logico() -> None:
    columnas = set(Paciente.__table__.columns.keys())

    assert columnas.isdisjoint(COLUMNAS_DE_BORRADO_LOGICO)


def test_paciente_declara_los_tres_indices_de_busqueda() -> None:
    indices = _indices(Paciente.__table__)

    assert indices.get("ix_paciente_tenant_id_telefono") == ("tenant_id", "telefono")
    assert indices.get("ix_paciente_tenant_id_creado_por_usuario_id") == (
        "tenant_id",
        "creado_por_usuario_id",
    )
    trigram = indices.get("ix_paciente_tenant_id_nombre_trgm")
    assert trigram is not None
    assert "tenant_id" in trigram


def test_paciente_tiene_timestamps_con_zona() -> None:
    for nombre in ("creado_en", "actualizado_en"):
        columna = Paciente.__table__.c[nombre]
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone is True
        assert columna.nullable is False
        assert columna.server_default is not None


def test_check_de_telefono_solo_admite_digitos(session_factory: sessionmaker[Session]) -> None:
    from sqlalchemy.exc import IntegrityError

    with session_factory() as session:
        tenant = crear_tenant(session)
        session.add(
            Paciente(
                tenant_id=tenant.id,
                nombre="Paciente Ficticio",
                telefono="11-4555-0001",
            )
        )
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "ck_paciente_telefono_digitos"


def test_borrar_el_usuario_creador_deja_el_paciente_sin_creador(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        usuario = crear_usuario(session, tenant, "creador@demo")
        paciente = Paciente(
            tenant_id=tenant.id,
            nombre="Paciente Ficticio",
            telefono="1145550001",
            creado_por_usuario_id=usuario.id,
        )
        session.add(paciente)
        session.commit()
        paciente_id = paciente.id
        usuario_id = usuario.id

        session.delete(session.get(Usuario, usuario_id))
        session.commit()

    with session_factory() as session:
        recargado = session.get(Paciente, paciente_id)
        assert recargado is not None
        assert recargado.creado_por_usuario_id is None


def test_el_indice_trigram_es_gin_trgm_en_la_base(
    db_engine: Engine,
) -> None:
    with db_engine.connect() as conexion:
        definiciones = (
            conexion.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'paciente'"
                )
            )
            .scalars()
            .all()
        )

    trigram = [definicion for definicion in definiciones if "gin_trgm_ops" in definicion]
    assert len(trigram) == 1
    assert "lower(" in trigram[0].lower()
    assert "nombre" in trigram[0].lower()


def test_downgrade_elimina_y_upgrade_recrea_la_tabla(db_url: str, db_engine: Engine) -> None:
    from alembic import command

    config = _alembic_config(db_url)
    try:
        with _database_url(db_url):
            command.downgrade(config, "0003_c04_profesional_prestacion")
        assert inspect(db_engine).has_table("paciente") is False

        with _database_url(db_url):
            command.upgrade(config, "head")
        assert inspect(db_engine).has_table("paciente") is True
    finally:
        with _database_url(db_url):
            command.upgrade(config, "head")

    with db_engine.connect() as conexion:
        tablas = conexion.execute(
            text("SELECT to_regclass('public.paciente') IS NOT NULL")
        ).scalar_one()
    assert tablas is True
