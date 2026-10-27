"""Contrato de metadata: tenant/timestamps, FK, índices y nombres determinísticos."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import CITEXT

from app.db.models import Tenant, Usuario


def test_tenant_declara_slug_unico_e_id_uuid() -> None:
    tabla = Tenant.__table__

    assert tabla.name == "tenant"
    assert tabla.primary_key.name == "pk_tenant"
    assert isinstance(tabla.c.id.type, Uuid)
    assert tabla.c.id.server_default is not None

    assert isinstance(tabla.c.slug.type, String)
    assert tabla.c.slug.nullable is False
    uniques = {c.name for c in tabla.constraints if isinstance(c, UniqueConstraint)}
    assert "uq_tenant_slug" in uniques

    assert tabla.c.nombre.nullable is False


def test_tenant_tiene_timestamps_con_zona() -> None:
    tabla = Tenant.__table__
    for nombre in ("creado_en", "actualizado_en"):
        columna = tabla.c[nombre]
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone is True
        assert columna.nullable is False
        assert columna.server_default is not None


def test_usuario_tenant_id_es_uuid_not_null_con_fk() -> None:
    tabla = Usuario.__table__

    assert tabla.name == "usuario"
    assert tabla.primary_key.name == "pk_usuario"
    columna = tabla.c.tenant_id
    assert isinstance(columna.type, Uuid)
    assert columna.nullable is False

    fks = list(columna.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column is Tenant.__table__.c.id
    assert fks[0].constraint.name == "fk_usuario_tenant_id_tenant"


def test_usuario_email_es_citext_y_password_not_null() -> None:
    tabla = Usuario.__table__

    assert isinstance(tabla.c.email.type, CITEXT)
    assert tabla.c.email.nullable is False
    assert tabla.c.password_hash.nullable is False
    assert tabla.c.nombre.nullable is False
    assert tabla.c.rol.nullable is False
    assert tabla.c.rol.type.length == 20
    assert tabla.c.activo.nullable is False
    assert tabla.c.es_dueno.nullable is False


def test_usuario_indices_compuestos_empiezan_por_tenant_id() -> None:
    tabla = Usuario.__table__

    compuestos = [indice for indice in tabla.indexes if len(indice.columns) > 1]
    assert compuestos, "Usuario debe tener índices compuestos por tenant"
    for indice in compuestos:
        primera = next(iter(indice.columns))
        assert primera.name == "tenant_id"

    assert "ix_usuario_tenant_id_rol" in {indice.name for indice in tabla.indexes}
    uniques = {c.name for c in tabla.constraints if isinstance(c, UniqueConstraint)}
    assert "uq_usuario_tenant_id_email" in uniques


def test_usuario_constraints_tienen_nombres_deterministicos() -> None:
    tabla = Usuario.__table__
    checks = {c.name for c in tabla.constraints if isinstance(c, CheckConstraint)}

    assert "ck_usuario_rol" in checks
    assert "ck_usuario_dueno_profesional" in checks


def test_usuario_timestamps_con_zona_y_actualizacion() -> None:
    tabla = Usuario.__table__
    for nombre in ("creado_en", "actualizado_en"):
        columna = tabla.c[nombre]
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone is True
        assert columna.nullable is False
        assert columna.server_default is not None
    assert tabla.c.actualizado_en.onupdate is not None
