"""Fábrica de usuarios con contraseña real: el hash debe verificar con Argon2id."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import verify_password
from app.db.models import RolUsuario
from tests.factories import PASSWORD_FICTICIO, crear_tenant, crear_usuario_con_password

pytestmark = pytest.mark.integration


def test_fabrica_genera_un_hash_argon2_verificable(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        usuario = crear_usuario_con_password(
            session,
            tenant,
            "dueno@demo",
            "clave-ficticia-2026",
            rol=RolUsuario.PROFESIONAL,
            es_dueno=True,
        )

    assert usuario.password_hash != "clave-ficticia-2026"
    assert usuario.password_hash.startswith("$argon2id$")
    assert verify_password("clave-ficticia-2026", usuario.password_hash) is True
    assert verify_password("clave-distinta-2026", usuario.password_hash) is False


def test_fabrica_respeta_los_datos_de_identidad(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session, "otro", "Consultorio Otro")
        usuario = crear_usuario_con_password(
            session, tenant, "recepcion@otro", "otra-clave-ficticia"
        )

    assert usuario.email == "recepcion@otro"
    assert usuario.tenant_id == tenant.id
    assert usuario.rol == RolUsuario.RECEPCION
    assert usuario.es_dueno is False
    assert usuario.activo is True


def test_password_ficticio_heredado_no_verifica() -> None:
    assert verify_password("cualquier-clave", PASSWORD_FICTICIO) is False
