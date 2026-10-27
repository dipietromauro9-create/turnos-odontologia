"""Constraints reales en Postgres: slug, email citext y regla de dueño (RN-AU-02)."""

from __future__ import annotations

import time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RolUsuario, SlugInmutableError, Tenant, Usuario
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


def test_slug_duplicado_es_rechazado_por_la_base(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        crear_tenant(session, "demo")
        session.add(Tenant(slug="demo", nombre="Otro Consultorio"))
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "uq_tenant_slug"


def test_slug_no_cambia_despues_de_creado(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        tenant_id = crear_tenant(session, "demo").id
        tenant = session.get(Tenant, tenant_id)
        assert tenant is not None
        tenant.slug = "otro-slug"
        with pytest.raises(SlugInmutableError):
            session.commit()
        session.rollback()

    with session_factory() as session:
        tenant = session.get(Tenant, tenant_id)
        assert tenant is not None
        assert tenant.slug == "demo"


def test_email_duplicado_case_insensitive_en_el_mismo_tenant(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        crear_usuario(session, tenant, "Dueno@Demo")
        with pytest.raises(IntegrityError) as exc:
            crear_usuario(session, tenant, "dueno@demo")
        assert exc.value.orig.diag.constraint_name == "uq_usuario_tenant_id_email"


def test_email_actualizado_a_duplicado_tambien_se_rechaza(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        crear_usuario(session, tenant, "dueno@demo")
        otro = crear_usuario(session, tenant, "recepcion@demo")
        otro.email = "DUENO@DEMO"
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        assert exc.value.orig.diag.constraint_name == "uq_usuario_tenant_id_email"


def test_mismo_email_en_otro_tenant_es_valido(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant_a = crear_tenant(session, "demo")
        tenant_b = crear_tenant(session, "otro")
        crear_usuario(session, tenant_a, "dueno@demo")
        crear_usuario(session, tenant_b, "dueno@demo")

        emails = session.query(Usuario.email).order_by(Usuario.email).all()
        assert len(emails) == 2


def test_recepcion_no_puede_ser_dueno(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        with pytest.raises(IntegrityError) as exc:
            crear_usuario(
                session,
                tenant,
                "recepcion@demo",
                RolUsuario.RECEPCION,
                es_dueno=True,
            )
        assert exc.value.orig.diag.constraint_name == "ck_usuario_dueno_profesional"


def test_profesional_dueno_es_valido(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        usuario = crear_usuario(
            session,
            tenant,
            "dueno@demo",
            RolUsuario.PROFESIONAL,
            es_dueno=True,
        )
        assert usuario.es_dueno is True
        assert usuario.rol is RolUsuario.PROFESIONAL


def test_actualizado_en_avanza_y_creado_en_no_cambia(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        usuario = crear_usuario(session, tenant, "dueno@demo")
        usuario_id = usuario.id
        creado_en = usuario.creado_en
        actualizado_en = usuario.actualizado_en

        time.sleep(0.01)
        usuario.nombre = "Otro Nombre Ficticio"
        session.commit()

    with session_factory() as session:
        actualizado = session.get(Usuario, usuario_id)
        assert actualizado is not None
        assert actualizado.creado_en == creado_en
        assert actualizado.actualizado_en > actualizado_en
