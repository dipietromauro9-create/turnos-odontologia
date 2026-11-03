"""Seed demo de dos pacientes ficticios, idempotente y sin PII real (R9)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Paciente, Tenant, Usuario
from app.db.seed import run_seed
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration

NOMBRES_DEMO = {"Paciente Demo Uno", "Paciente Demo Dos"}
TELEFONOS_DEMO = {"1145550001", "1145550002"}


def _pacientes_demo(session: Session) -> list[Paciente]:
    tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
    return list(session.execute(select(Paciente).where(Paciente.tenant_id == tenant.id)).scalars())


def test_el_seed_crea_dos_pacientes_ficticios_del_dueno(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    resultado = run_seed()

    with session_factory() as session:
        pacientes = _pacientes_demo(session)
        dueno = session.execute(select(Usuario).where(Usuario.email == "dueno@demo")).scalar_one()

    assert resultado["pacientes_creados"] == 2
    assert {p.nombre for p in pacientes} == NOMBRES_DEMO
    assert {p.telefono for p in pacientes} == TELEFONOS_DEMO
    assert {p.creado_por_usuario_id for p in pacientes} == {dueno.id}


def test_reejecutar_el_seed_no_duplica_ni_sobreescribe(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    run_seed()
    with session_factory() as session:
        antes = sorted((p.id, p.nombre, p.telefono) for p in _pacientes_demo(session))

    segundo = run_seed()

    with session_factory() as session:
        despues = sorted((p.id, p.nombre, p.telefono) for p in _pacientes_demo(session))
    assert segundo["pacientes_creados"] == 0
    assert despues == antes


def test_un_paciente_demo_existente_no_se_duplica_ni_se_pisa(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        dueno = crear_usuario(session, tenant, "persona@demo", nombre="Dueño Ficticio")
        session.add(
            Paciente(
                tenant_id=tenant.id,
                nombre="Nombre Personalizado",
                telefono="1145550001",
                creado_por_usuario_id=dueno.id,
            )
        )
        session.commit()

    run_seed()

    with session_factory() as session:
        pacientes = _pacientes_demo(session)
        personalizado = session.execute(
            select(Paciente).where(Paciente.telefono == "1145550001")
        ).scalar_one()
    assert len(pacientes) == 2
    assert personalizado.nombre == "Nombre Personalizado"


def test_los_pacientes_demo_no_aparecen_en_otro_tenant(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        ajeno = Paciente(tenant_id=otro.id, nombre="Ajeno Ficticio", telefono="1145550001")
        session.add(ajeno)
        session.commit()
        otro_id = otro.id

    run_seed()

    with session_factory() as session:
        del_otro = list(
            session.execute(select(Paciente).where(Paciente.tenant_id == otro_id)).scalars()
        )
    assert len(del_otro) == 1
    assert del_otro[0].nombre == "Ajeno Ficticio"


def test_los_datos_demo_son_ficticios_y_documentados(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    run_seed()

    with session_factory() as session:
        pacientes = _pacientes_demo(session)

    for paciente in pacientes:
        assert paciente.nombre.startswith("Paciente Demo")
        assert paciente.telefono in TELEFONOS_DEMO
        assert paciente.documento is None
        assert paciente.fecha_nac is None
