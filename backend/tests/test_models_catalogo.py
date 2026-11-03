"""Metadata del catálogo: modelos `Profesional`/`Prestacion` con frontera de tenant."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AuditMixin,
    Prestacion,
    Profesional,
    Tenant,
    TenantMixin,
    Usuario,
)
from tests.factories import (
    crear_prestacion,
    crear_profesional,
    crear_tenant,
    crear_usuario,
)

pytestmark = pytest.mark.integration


def test_profesional_declara_frontera_de_tenant_y_auditoria() -> None:
    tabla = Profesional.__table__

    assert issubclass(Profesional, TenantMixin)
    assert issubclass(Profesional, AuditMixin)
    assert tabla.name == "profesional"
    assert tabla.primary_key.name == "pk_profesional"

    assert isinstance(tabla.c.id.type, Uuid)
    assert tabla.c.id.server_default is not None

    tenant_id = tabla.c.tenant_id
    assert isinstance(tenant_id.type, Uuid)
    assert tenant_id.nullable is False
    fks_tenant = list(tenant_id.foreign_keys)
    assert len(fks_tenant) == 1
    assert fks_tenant[0].column is Tenant.__table__.c.id
    assert fks_tenant[0].constraint.name == "fk_profesional_tenant_id_tenant"


def test_profesional_vincula_usuario_opcional_y_declara_unicidad_global() -> None:
    tabla = Profesional.__table__

    usuario_id = tabla.c.usuario_id
    assert isinstance(usuario_id.type, Uuid)
    assert usuario_id.nullable is True
    fks_usuario = list(usuario_id.foreign_keys)
    assert len(fks_usuario) == 1
    assert fks_usuario[0].column is Usuario.__table__.c.id
    assert fks_usuario[0].constraint.name == "fk_profesional_usuario_id_usuario"
    assert isinstance(fks_usuario[0], ForeignKey)

    uniques = [c for c in tabla.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any(
        tuple(columna.name for columna in unique.columns) == ("usuario_id",) for unique in uniques
    )


def test_profesional_declara_campos_y_flag_activo() -> None:
    tabla = Profesional.__table__

    assert isinstance(tabla.c.nombre.type, String)
    assert tabla.c.nombre.nullable is False
    assert tabla.c.matricula.nullable is True
    assert tabla.c.especialidad.nullable is True

    assert isinstance(tabla.c.activo.type, Boolean)
    assert tabla.c.activo.nullable is False
    assert tabla.c.activo.server_default is not None


def test_profesional_declara_indice_por_tenant_y_activo() -> None:
    indices = {
        indice.name: tuple(columna.name for columna in indice.columns)
        for indice in Profesional.__table__.indexes
    }

    assert indices.get("ix_profesional_tenant_id_activo") == ("tenant_id", "activo")


def test_profesional_tiene_timestamps_con_zona() -> None:
    tabla = Profesional.__table__
    for nombre in ("creado_en", "actualizado_en"):
        columna = tabla.c[nombre]
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone is True
        assert columna.nullable is False
        assert columna.server_default is not None


def test_prestacion_declara_frontera_de_tenant_y_auditoria() -> None:
    tabla = Prestacion.__table__

    assert issubclass(Prestacion, TenantMixin)
    assert issubclass(Prestacion, AuditMixin)
    assert tabla.name == "prestacion"
    assert tabla.primary_key.name == "pk_prestacion"

    assert isinstance(tabla.c.id.type, Uuid)
    assert tabla.c.id.server_default is not None

    tenant_id = tabla.c.tenant_id
    assert isinstance(tenant_id.type, Uuid)
    assert tenant_id.nullable is False
    fks_tenant = list(tenant_id.foreign_keys)
    assert len(fks_tenant) == 1
    assert fks_tenant[0].column is Tenant.__table__.c.id
    assert fks_tenant[0].constraint.name == "fk_prestacion_tenant_id_tenant"


def test_prestacion_duracion_entera_y_precio_numeric_opcional() -> None:
    tabla = Prestacion.__table__

    assert isinstance(tabla.c.nombre.type, String)
    assert tabla.c.nombre.nullable is False

    duracion = tabla.c.duracion_min
    assert isinstance(duracion.type, Integer)
    assert duracion.nullable is False

    precio = tabla.c.precio_ref
    assert isinstance(precio.type, Numeric)
    assert precio.type.precision == 12
    assert precio.type.scale == 2
    assert precio.nullable is True


def test_prestacion_declara_flag_activa_e_indice() -> None:
    tabla = Prestacion.__table__

    assert isinstance(tabla.c.activa.type, Boolean)
    assert tabla.c.activa.nullable is False
    assert tabla.c.activa.server_default is not None

    indices = {
        indice.name: tuple(columna.name for columna in indice.columns) for indice in tabla.indexes
    }
    assert indices.get("ix_prestacion_tenant_id_activa") == ("tenant_id", "activa")


def test_prestacion_declara_checks_de_duracion_y_precio() -> None:
    tabla = Prestacion.__table__
    checks = {c.name: str(c.sqltext) for c in tabla.constraints if isinstance(c, CheckConstraint)}

    assert "duracion_min % 5 = 0" in checks["ck_prestacion_duracion_multiplo_5"]
    assert "duracion_min > 0" in checks["ck_prestacion_duracion_multiplo_5"]
    assert "precio_ref IS NULL OR precio_ref >= 0" in checks["ck_prestacion_precio_no_negativo"]


def test_prestacion_tiene_timestamps_con_zona() -> None:
    tabla = Prestacion.__table__
    for nombre in ("creado_en", "actualizado_en"):
        columna = tabla.c[nombre]
        assert isinstance(columna.type, DateTime)
        assert columna.type.timezone is True
        assert columna.nullable is False
        assert columna.server_default is not None


def test_usuario_ya_vinculado_es_rechazado_por_unicidad(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        usuario = crear_usuario(session, tenant, "profesional@demo")
        crear_profesional(session, tenant, usuario=usuario)

        session.add(
            Profesional(
                tenant_id=tenant.id,
                usuario_id=usuario.id,
                nombre="Otro Profesional Ficticio",
            )
        )
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "uq_profesional_usuario_id"


def test_dos_profesionales_sin_usuario_son_validos(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        crear_profesional(session, tenant, nombre="Profesional A")
        crear_profesional(session, tenant, nombre="Profesional B")

        sin_usuario = session.query(Profesional).filter(Profesional.usuario_id.is_(None)).count()
        assert sin_usuario == 2


@pytest.mark.parametrize("duracion", [0, -5, 33])
def test_duracion_invalida_es_rechazada_por_el_check(
    session_factory: sessionmaker[Session], duracion: int
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        with pytest.raises(IntegrityError) as exc:
            crear_prestacion(session, tenant, duracion_min=duracion)
        assert exc.value.orig.diag.constraint_name == "ck_prestacion_duracion_multiplo_5"


@pytest.mark.parametrize("duracion", [5, 20, 30, 45, 60])
def test_duracion_multiplo_positivo_de_cinco_es_aceptada(
    session_factory: sessionmaker[Session], duracion: int
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        prestacion = crear_prestacion(session, tenant, duracion_min=duracion)
        assert prestacion.duracion_min == duracion


def test_precio_nulo_es_aceptado_y_negativo_rechazado(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        sin_precio = crear_prestacion(session, tenant, nombre="Sin precio")
        assert sin_precio.precio_ref is None

    with session_factory() as session:
        tenant = crear_tenant(session, "otro", "Consultorio Otro")
        with pytest.raises(IntegrityError) as exc:
            crear_prestacion(session, tenant, precio_ref=Decimal("-0.01"))
        assert exc.value.orig.diag.constraint_name == "ck_prestacion_precio_no_negativo"


def test_actualizado_en_avanza_y_creado_en_no_cambia(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        prestacion = crear_prestacion(session, tenant)
        prestacion_id = prestacion.id
        creado_en = prestacion.creado_en
        actualizado_en = prestacion.actualizado_en

        time.sleep(0.01)
        prestacion.nombre = "Prestación Renombrada"
        session.commit()

    with session_factory() as session:
        actualizada = session.get(Prestacion, prestacion_id)
        assert actualizada is not None
        assert actualizada.creado_en == creado_en
        assert actualizada.actualizado_en > actualizado_en
