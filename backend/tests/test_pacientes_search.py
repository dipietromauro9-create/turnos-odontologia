"""Búsqueda de pacientes: trigram por nombre, dígitos por teléfono y aislamiento."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Paciente, Tenant, Usuario
from app.db.session import tenant_context, tenant_session
from app.domain.pacientes.dependencies import alcance_pacientes
from app.domain.pacientes.service import buscar_pacientes
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Entorno:
    tenant: Tenant
    recepcion: Usuario


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Entorno:
    with session_factory() as session:
        tenant = crear_tenant(session)
        recepcion = crear_usuario(session, tenant, "recepcion@demo")
    return Entorno(tenant=tenant, recepcion=recepcion)


def _sembrar(
    entorno: Entorno,
    session_factory: sessionmaker[Session],
    filas: list[tuple[str, str]],
) -> list[Paciente]:
    with tenant_session(entorno.tenant.id) as session:
        pacientes = [
            Paciente(
                tenant_id=entorno.tenant.id,
                nombre=nombre,
                telefono=telefono,
                creado_por_usuario_id=entorno.recepcion.id,
            )
            for nombre, telefono in filas
        ]
        session.add_all(pacientes)
        session.commit()
        return pacientes


def _buscar(entorno: Entorno, **kwargs: object) -> list[Paciente]:
    with (
        tenant_context(entorno.tenant.id, entorno.tenant.slug),
        tenant_session(entorno.tenant.id) as session,
    ):
        return buscar_pacientes(
            session,
            alcance=alcance_pacientes(entorno.recepcion),
            usuario_id=entorno.recepcion.id,
            **kwargs,
        )


def test_un_nombre_con_error_de_tipeo_encuentra_por_trigram(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(entorno, session_factory, [("María González", "1145550001")])

    resultados = _buscar(entorno, q="maria gonzales")

    assert [paciente.nombre for paciente in resultados] == ["María González"]


@pytest.mark.parametrize("consulta", ["11 4555-0001", "1145550001"])
def test_el_telefono_se_encuentra_con_o_sin_formato(
    entorno: Entorno, session_factory: sessionmaker[Session], consulta: str
) -> None:
    _sembrar(entorno, session_factory, [("María González", "1145550001")])

    resultados = _buscar(entorno, q=consulta)

    assert [paciente.nombre for paciente in resultados] == ["María González"]


def test_sin_termino_lista_ordenado_por_nombre(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(
        entorno,
        session_factory,
        [("Zulema Ficticia", "1145550003"), ("Ana Ficticia", "1145550001")],
    )

    resultados = _buscar(entorno)

    assert [paciente.nombre for paciente in resultados] == ["Ana Ficticia", "Zulema Ficticia"]


def test_limit_y_offset_recortan_el_resultado(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(
        entorno,
        session_factory,
        [
            ("Ana Ficticia", "1145550001"),
            ("Beto Ficticio", "1145550002"),
            ("Carla Ficticia", "1145550003"),
        ],
    )

    primera_pagina = _buscar(entorno, limit=2)
    segunda_pagina = _buscar(entorno, limit=2, offset=2)

    assert [paciente.nombre for paciente in primera_pagina] == ["Ana Ficticia", "Beto Ficticio"]
    assert [paciente.nombre for paciente in segunda_pagina] == ["Carla Ficticia"]


def test_la_busqueda_no_cruza_el_tenant(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        otro = crear_tenant(session, "otro", "Consultorio Otro")
        session.add(Paciente(tenant_id=otro.id, nombre="María González", telefono="1145550001"))
        session.commit()
    _sembrar(entorno, session_factory, [("María González", "1145550002")])

    resultados = _buscar(entorno, q="maria gonzalez")

    assert [paciente.tenant_id for paciente in resultados] == [entorno.tenant.id]


def test_un_termino_corto_usa_solo_ilike(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    from sqlalchemy.dialects import postgresql

    from app.domain.pacientes.service import _consulta_busqueda

    _sembrar(entorno, session_factory, [("María González", "1145550001")])

    corta, _ = _consulta_busqueda(
        tenant_id=entorno.tenant.id,
        q="ma",
        alcance=alcance_pacientes(entorno.recepcion),
        usuario_id=entorno.recepcion.id,
    )
    sql_corta = str(corta.compile(dialect=postgresql.dialect()))

    assert "LIKE" in sql_corta
    assert "similarity" not in sql_corta
    assert [p.nombre for p in _buscar(entorno, q="ma")] == ["María González"]


def test_la_busqueda_no_distingue_mayusculas(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(entorno, session_factory, [("María González", "1145550001")])

    assert [p.nombre for p in _buscar(entorno, q="MARÍA GONZÁLEZ")] == ["María González"]


def test_una_busqueda_sin_resultados_devuelve_lista_vacia(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(entorno, session_factory, [("María González", "1145550001")])

    assert _buscar(entorno, q="zzzzzzzz") == []


def test_limit_mayor_al_maximo_se_recorta_y_menor_a_uno_se_ajusta(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    _sembrar(
        entorno,
        session_factory,
        [(f"Paciente {indice:03d}", f"114555{indice:04d}") for indice in range(101)],
    )

    assert len(_buscar(entorno, limit=1000)) == 100
    assert len(_buscar(entorno, limit=0)) == 1


def test_el_plan_por_nombre_usa_el_indice_trigram(
    entorno: Entorno, session_factory: sessionmaker[Session]
) -> None:
    from sqlalchemy import select, text
    from sqlalchemy.dialects import postgresql

    from app.domain.pacientes.service import _condicion_trigram

    _sembrar(entorno, session_factory, [("María González", "1145550001")])
    consulta = select(Paciente).where(
        Paciente.tenant_id == entorno.tenant.id,
        _condicion_trigram("maria gonzales"),
    )
    sql = str(
        consulta.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).replace("%%", "%")

    with session_factory() as session:
        session.execute(text("SET LOCAL enable_seqscan = off"))
        # Los btrees de tenant ganan el plan con pocas filas; se quitan solo
        # dentro de la transacción para aislar la capacidad del índice trigram.
        session.execute(text("DROP INDEX ix_paciente_tenant_id_creado_por_usuario_id"))
        session.execute(text("DROP INDEX ix_paciente_tenant_id_telefono"))
        plan = session.execute(text("EXPLAIN " + sql)).scalars().all()
        session.rollback()

    assert any("ix_paciente_tenant_id_nombre_trgm" in linea for linea in plan)
    assert any("Index Cond" in linea and "%" in linea for linea in plan)
