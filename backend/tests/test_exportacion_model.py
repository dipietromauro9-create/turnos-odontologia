"""Modelo `Exportacion` y migración `0008_exportacion`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AuditMixin,
    EstadoExportacion,
    Exportacion,
    RolUsuario,
    TenantMixin,
    TipoExportacion,
)
from app.db.session import tenant_session
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


def _fila(tenant_id: uuid.UUID, **cambios: object) -> Exportacion:
    datos: dict[str, object] = {
        "tenant_id": tenant_id,
        "tipo": TipoExportacion.TURNOS,
        "estado": EstadoExportacion.PENDIENTE,
    }
    datos.update(cambios)
    return Exportacion(**datos)


def test_exportacion_metadata_frontera_referencias_e_indices() -> None:
    tabla = Exportacion.__table__
    assert issubclass(Exportacion, TenantMixin) and issubclass(Exportacion, AuditMixin)
    assert not tabla.c.tenant_id.nullable

    fk_tenant = next(iter(tabla.c.tenant_id.foreign_keys))
    assert fk_tenant.target_fullname == "tenant.id"
    fk_usuario = next(iter(tabla.c.creado_por.foreign_keys))
    assert fk_usuario.target_fullname == "usuario.id" and fk_usuario.ondelete == "SET NULL"

    indices = {tuple(i.columns.keys()) for i in tabla.indexes}
    assert ("tenant_id", "estado") in indices
    assert ("tenant_id", "creado_en") in indices
    for campo in ("desde", "hasta", "creado_en", "actualizado_en"):
        assert isinstance(tabla.c[campo].type, DateTime) and tabla.c[campo].type.timezone


def test_migracion_crea_tabla_y_enums(db_engine: Engine) -> None:
    assert inspect(db_engine).has_table("exportacion")
    with db_engine.connect() as conn:
        etiquetas = {
            (fila[0], fila[1])
            for fila in conn.execute(
                text(
                    "SELECT t.typname, e.enumlabel FROM pg_type t "
                    "JOIN pg_enum e ON e.enumtypid = t.oid "
                    "WHERE t.typname IN ('tipo_exportacion', 'estado_exportacion')"
                )
            )
        }
    assert ("tipo_exportacion", "turnos") in etiquetas
    assert ("tipo_exportacion", "pacientes") in etiquetas
    assert {etiqueta for tipo, etiqueta in etiquetas if tipo == "estado_exportacion"} == {
        "pendiente",
        "procesando",
        "listo",
        "fallido",
    }


def test_estado_por_defecto_es_pendiente(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        fila = Exportacion(tenant_id=tenant.id, tipo=TipoExportacion.PACIENTES)
        session.add(fila)
        session.commit()
        session.refresh(fila)
        assert fila.estado is EstadoExportacion.PENDIENTE


def test_contenido_y_error_son_opcionales_y_persisten(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        contenido = "x" * 10_000
        fila = _fila(
            tenant.id,
            estado=EstadoExportacion.LISTO,
            contenido=contenido,
            desde=datetime(2030, 6, 1, tzinfo=UTC),
            hasta=datetime(2030, 6, 30, tzinfo=UTC),
        )
        session.add(fila)
        session.commit()
        session.refresh(fila)
        assert fila.contenido == contenido
        assert fila.error is None


def test_borrado_del_usuario_deja_creado_por_nulo(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        usuario = crear_usuario(
            session, tenant, "dueno@demo", RolUsuario.PROFESIONAL, es_dueno=True
        )
        fila = _fila(tenant.id, creado_por=usuario.id)
        session.add(fila)
        session.commit()
        session.execute(text("DELETE FROM usuario WHERE id = :id"), {"id": usuario.id})
        session.commit()
        session.refresh(fila)
        assert fila.creado_por is None


def test_lectura_aislada_por_tenant(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        demo = crear_tenant(session, "demo")
        otro = crear_tenant(session, "otro")
        session.add(_fila(demo.id))
        session.add(_fila(otro.id))
        session.commit()
        demo_id = demo.id

    with tenant_session(demo_id) as session:
        filas = session.query(Exportacion).all()
        assert len(filas) == 1 and filas[0].tenant_id == demo_id


def test_escritura_de_otro_tenant_se_rechaza(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    from app.db.session import TenantIsolationError

    with session_factory() as session:
        demo = crear_tenant(session, "demo")
        otro = crear_tenant(session, "otro")
        ajena = _fila(otro.id)

    with tenant_session(demo.id) as session:
        session.add(ajena)
        with pytest.raises(TenantIsolationError):
            session.flush()
