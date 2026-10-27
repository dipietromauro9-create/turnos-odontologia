"""Repositorio tenant-scoped y unidad de trabajo atómica (R3, RN-GL-02)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RolUsuario, Tenant, Usuario
from app.db.session import TenantNotResolvedError, tenant_context
from app.domain.persistence import BaseRepository, UnitOfWork
from tests.factories import PASSWORD_FICTICIO, crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


@pytest.fixture()
def tenants(session_factory: sessionmaker[Session]) -> dict[str, Tenant]:
    with session_factory() as session:
        demo = crear_tenant(session, "demo")
        otro = crear_tenant(session, "otro")
        crear_usuario(session, demo, "dueno@demo", RolUsuario.PROFESIONAL, es_dueno=True)
        crear_usuario(session, otro, "dueno@otro", RolUsuario.PROFESIONAL)
        return {"demo": demo, "otro": otro}


def _usuario(email: str, tenant_id: object | None = None) -> Usuario:
    return Usuario(
        tenant_id=tenant_id,  # type: ignore[arg-type]
        nombre="Persona Ficticia",
        email=email,
        password_hash=PASSWORD_FICTICIO,
        rol=RolUsuario.RECEPCION,
        es_dueno=False,
        activo=True,
    )


def test_listar_y_obtener_solo_del_tenant_de_la_sesion(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        usuario_otro_id = session.execute(
            select(Usuario.id).where(Usuario.email == "dueno@otro")
        ).scalar_one()

    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        repositorio = uow.repository(Usuario)
        emails = sorted(u.email for u in repositorio.list())

    assert emails == ["dueno@demo"]
    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        assert uow.repository(Usuario).get(usuario_otro_id) is None


def test_crear_desde_el_repositorio_asigna_el_tenant_de_la_sesion(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        creado = uow.repository(Usuario).add(_usuario("nuevo@demo", tenant_id=tenants["otro"].id))
        creado_id = creado.id

    assert creado.tenant_id == tenants["demo"].id
    with session_factory() as session:
        persistido = session.get(Usuario, creado_id)
        assert persistido is not None
        assert persistido.tenant_id == tenants["demo"].id


def test_repositorio_sin_sesion_tenant_scoped_falla(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session, pytest.raises(RuntimeError, match="tenant"):
        BaseRepository(session, Usuario)


def test_uow_sin_tenant_resuelto_falla(app_env: None) -> None:
    with pytest.raises(TenantNotResolvedError):
        UnitOfWork()


def test_uow_persiste_todo_el_grupo_al_cerrar(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        repositorio = uow.repository(Usuario)
        repositorio.add(_usuario("uno@demo"))
        repositorio.add(_usuario("dos@demo"))

    with session_factory() as session:
        emails = sorted(
            session.execute(select(Usuario.email).where(Usuario.email.like("%@demo"))).scalars()
        )
    assert emails == ["dos@demo", "dueno@demo", "uno@demo"]


def test_uow_revierte_todo_ante_un_fallo_intermedio(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    with (
        pytest.raises(RuntimeError, match="falla simulada"),
        tenant_context(tenants["demo"].id, "demo"),
        UnitOfWork() as uow,
    ):
        uow.repository(Usuario).add(_usuario("uno@demo"))
        raise RuntimeError("falla simulada")

    with session_factory() as session:
        emails = (
            session.execute(select(Usuario.email).where(Usuario.email == "uno@demo"))
            .scalars()
            .all()
        )
    assert emails == []


def test_update_y_delete_de_otro_tenant_no_tocan_la_fila(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        ajeno = session.execute(select(Usuario).where(Usuario.email == "dueno@otro")).scalar_one()
        ajeno_id = ajeno.id

    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        repositorio = uow.repository(Usuario)
        assert repositorio.get(ajeno_id) is None
        assert repositorio.update(ajeno_id, nombre="Hackeado Ficticio") is None
        assert repositorio.delete(ajeno_id) is False

    with session_factory() as session:
        sigue = session.get(Usuario, ajeno_id)
        assert sigue is not None
        assert sigue.nombre == "Persona Ficticia"


def test_otra_sesion_no_ve_escrituras_antes_del_commit(
    app_env: None, tenants: dict[str, Tenant], session_factory: sessionmaker[Session]
) -> None:
    def _visibles(email: str) -> list[str]:
        with session_factory() as externa:
            return list(
                externa.execute(select(Usuario.email).where(Usuario.email == email)).scalars()
            )

    with tenant_context(tenants["demo"].id, "demo"), UnitOfWork() as uow:
        uow.repository(Usuario).add(_usuario("pendiente@demo"))
        assert _visibles("pendiente@demo") == []

    assert _visibles("pendiente@demo") == ["pendiente@demo"]
