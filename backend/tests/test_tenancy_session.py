"""Resolución de tenant, health público y aislamiento de lectura por sesión."""

from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RolUsuario, Tenant, Usuario
from app.db.session import TenantContextMiddleware, get_session, tenant_session
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


def _app_de_dominio() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TenantContextMiddleware)

    @app.get("/usuarios")
    def listar(session: Annotated[Session, Depends(get_session)]) -> dict[str, int]:
        emails = session.execute(select(Usuario.email)).scalars().all()
        return {"total": len(emails)}

    return app


@pytest.fixture()
def dos_tenants(session_factory: sessionmaker[Session]) -> dict[str, Tenant]:
    with session_factory() as session:
        demo = crear_tenant(session, "demo", "Consultorio Demo")
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        crear_usuario(
            session,
            demo,
            "dueno@demo",
            RolUsuario.PROFESIONAL,
            es_dueno=True,
        )
        crear_usuario(session, demo, "recepcion@demo")
        crear_usuario(session, otro, "dueno@otro", RolUsuario.PROFESIONAL)
        return {"demo": demo, "otro": otro}


def test_request_de_dominio_usa_el_tenant_por_defecto(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    client = TestClient(_app_de_dominio())

    respuesta = client.get("/usuarios")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 2}


def test_session_sin_tenant_falla_antes_de_consultar(app_env: None) -> None:
    generador = get_session()
    with pytest.raises(RuntimeError, match="tenant"):
        next(generador)


def test_health_sigue_publico_y_sin_tenant(app_env: None) -> None:
    from app.main import create_app

    client = TestClient(create_app())

    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_consulta_del_tenant_a_no_devuelve_filas_del_b(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    with tenant_session(dos_tenants["demo"].id) as session:
        emails = session.execute(select(Usuario.email)).scalars().all()

    assert sorted(emails) == ["dueno@demo", "recepcion@demo"]
    assert "dueno@otro" not in emails


def test_request_de_dominio_sin_tenant_configurado_falla_503(
    app_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings

    monkeypatch.setenv("TENANT_DEFAULT_SLUG", "inexistente")
    get_settings.cache_clear()

    client = TestClient(_app_de_dominio())

    respuesta = client.get("/usuarios")

    assert respuesta.status_code == 503
    assert "inexistente" in respuesta.json()["detail"]


def test_escritura_hacia_otro_tenant_se_rechaza(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    from app.db.session import TenantIsolationError

    with tenant_session(dos_tenants["demo"].id) as session:
        session.add(
            Usuario(
                tenant_id=dos_tenants["otro"].id,
                nombre="Intruso Ficticio",
                email="intruso@otro",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$hash$ficticio",
                rol=RolUsuario.RECEPCION,
            )
        )
        with pytest.raises(TenantIsolationError):
            session.commit()
        session.rollback()

    with tenant_session(dos_tenants["demo"].id) as session:
        emails = session.execute(select(Usuario.email)).scalars().all()
    assert "intruso@otro" not in emails


def test_mover_una_fila_propia_a_otro_tenant_se_rechaza(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    from app.db.session import TenantIsolationError

    with tenant_session(dos_tenants["demo"].id) as session:
        usuario = session.execute(
            select(Usuario).where(Usuario.email == "recepcion@demo")
        ).scalar_one()
        usuario.tenant_id = dos_tenants["otro"].id
        with pytest.raises(TenantIsolationError):
            session.commit()
        session.rollback()

    with tenant_session(dos_tenants["demo"].id) as session:
        sigue = session.execute(
            select(Usuario).where(Usuario.email == "recepcion@demo")
        ).scalar_one()
    assert sigue.tenant_id == dos_tenants["demo"].id


def test_alias_y_join_tambien_quedan_filtrados(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    from sqlalchemy.orm import aliased

    with tenant_session(dos_tenants["demo"].id) as session:
        alias = aliased(Usuario)
        por_alias = session.execute(select(alias.email)).scalars().all()
        por_join = (
            session.execute(select(Usuario.email).join(Tenant, Usuario.tenant_id == Tenant.id))
            .scalars()
            .all()
        )

    assert sorted(por_alias) == ["dueno@demo", "recepcion@demo"]
    assert sorted(por_join) == ["dueno@demo", "recepcion@demo"]


def test_el_resolver_cachea_el_slug_por_request(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    from sqlalchemy import event

    from app.db.session import get_engine, reset_tenant_cache, resolve_tenant

    reset_tenant_cache()
    engine = get_engine()
    consultas: list[str] = []

    def _contar(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        if "FROM tenant" in statement:
            consultas.append(statement)

    event.listen(engine, "before_cursor_execute", _contar)
    try:
        primera = resolve_tenant("demo")
        segunda = resolve_tenant("demo")
    finally:
        event.remove(engine, "before_cursor_execute", _contar)

    assert primera == segunda
    assert len(consultas) == 1


def test_aislamiento_bidireccional_entre_dos_tenants(
    app_env: None, dos_tenants: dict[str, Tenant]
) -> None:
    with tenant_session(dos_tenants["demo"].id) as session:
        demo = sorted(session.execute(select(Usuario.email)).scalars().all())
    with tenant_session(dos_tenants["otro"].id) as session:
        otro = sorted(session.execute(select(Usuario.email)).scalars().all())
    with tenant_session(dos_tenants["demo"].id) as session:
        demo_otra_vez = sorted(session.execute(select(Usuario.email)).scalars().all())

    assert demo == ["dueno@demo", "recepcion@demo"]
    assert otro == ["dueno@otro"]
    assert demo_otra_vez == demo
