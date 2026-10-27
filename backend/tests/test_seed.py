"""Seed demo idempotente: tenant + usuarios ficticios, sin datos de pacientes (R9)."""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RolUsuario, Tenant, Usuario
from app.db.seed import DEMO_PASSWORDS, run_seed

pytestmark = pytest.mark.integration


def _snapshot(session: Session) -> dict[str, object]:
    tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
    usuarios = (
        session.execute(
            select(Usuario).where(Usuario.tenant_id == tenant.id).order_by(Usuario.email)
        )
        .scalars()
        .all()
    )
    return {
        "tenant": (tenant.id, tenant.slug, tenant.nombre),
        "usuarios": [
            (u.id, u.email, u.nombre, u.rol, u.es_dueno, u.activo, u.password_hash)
            for u in usuarios
        ],
    }


def test_seed_crea_el_escenario_demo(app_env: None, session_factory: sessionmaker[Session]) -> None:
    run_seed()

    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        usuarios = {
            u.email: u
            for u in session.execute(
                select(Usuario).where(Usuario.tenant_id == tenant.id)
            ).scalars()
        }

    assert tenant.nombre == "Consultorio Demo"
    assert set(usuarios) == {"dueno@demo", "recepcion@demo"}

    dueno = usuarios["dueno@demo"]
    assert dueno.rol is RolUsuario.PROFESIONAL
    assert dueno.es_dueno is True
    assert dueno.activo is True

    recepcion = usuarios["recepcion@demo"]
    assert recepcion.rol is RolUsuario.RECEPCION
    assert recepcion.es_dueno is False
    assert recepcion.activo is True

    hasher = PasswordHasher()
    for email, usuario in usuarios.items():
        assert usuario.password_hash.startswith("$argon2id$")
        assert hasher.verify(usuario.password_hash, DEMO_PASSWORDS[email]) is True


def test_seed_no_crea_pacientes(app_env: None, db_engine: object) -> None:
    run_seed()

    tablas = set(inspect(db_engine).get_table_names())  # type: ignore[arg-type]
    assert "paciente" not in tablas
    with db_engine.connect() as conexion:  # type: ignore[union-attr]
        valor = conexion.execute(text("SELECT count(*) FROM usuario")).scalar_one()
    assert valor == 2


def test_seed_es_idempotente(app_env: None, session_factory: sessionmaker[Session]) -> None:
    run_seed()
    with session_factory() as session:
        primera = _snapshot(session)

    run_seed()
    with session_factory() as session:
        segunda = _snapshot(session)

    assert segunda == primera


def test_seed_no_pisa_un_tenant_existente(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        session.add(Tenant(slug="demo", nombre="Nombre Personalizado"))
        session.commit()

    run_seed()

    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        assert tenant.nombre == "Nombre Personalizado"


def test_seed_no_pisa_usuarios_existentes(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = Tenant(slug="demo", nombre="Consultorio Demo")
        session.add(tenant)
        session.flush()
        session.add(
            Usuario(
                tenant_id=tenant.id,
                nombre="Nombre Existente",
                email="dueno@demo",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$hash$existente",
                rol=RolUsuario.PROFESIONAL,
                es_dueno=True,
                activo=False,
            )
        )
        session.commit()

    run_seed()

    with session_factory() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        usuarios = {
            u.email: u
            for u in session.execute(
                select(Usuario).where(Usuario.tenant_id == tenant.id)
            ).scalars()
        }
    assert set(usuarios) == {"dueno@demo", "recepcion@demo"}
    assert usuarios["dueno@demo"].nombre == "Nombre Existente"
    assert usuarios["dueno@demo"].activo is False
    assert usuarios["dueno@demo"].password_hash.endswith("$existente")
