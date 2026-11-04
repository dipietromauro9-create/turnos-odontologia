"""Seed demo del catálogo: profesional vinculado, cinco prestaciones y disponibilidad."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Disponibilidad, Prestacion, Profesional, RolUsuario, Tenant, Usuario
from app.db.seed import run_seed
from tests.factories import crear_prestacion, crear_profesional, crear_tenant, crear_usuario

pytestmark = pytest.mark.integration

PRESTACIONES_DEMO: dict[str, int] = {
    "Consulta": 30,
    "Limpieza": 60,
    "Extracción": 45,
    "Control": 20,
    "Urgencia": 30,
}

_DDL_DISPONIBILIDAD = """
CREATE TABLE disponibilidad (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    profesional_id uuid NOT NULL,
    dia_semana integer NOT NULL,
    hora_desde time NOT NULL,
    hora_hasta time NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
)
"""


def _borrar_disponibilidad(engine: Engine) -> None:
    with engine.begin() as conexion:
        conexion.execute(text("DROP TABLE IF EXISTS disponibilidad"))


@pytest.fixture(autouse=True)
def sin_disponibilidad(db_engine: Engine) -> None:
    """Simula C-04 sin agenda y restaura siempre el esquema real de C-06."""
    _borrar_disponibilidad(db_engine)
    try:
        yield
    finally:
        _borrar_disponibilidad(db_engine)
        Disponibilidad.__table__.create(db_engine)


def _tenant(app_env: None, session_factory: sessionmaker[Session]) -> Tenant:
    run_seed()
    with session_factory() as session:
        return session.query(Tenant).filter(Tenant.slug == "demo").one()


def _prestaciones(session_factory: sessionmaker[Session], tenant: Tenant) -> dict[str, Prestacion]:
    with session_factory() as session:
        return {
            prestacion.nombre: prestacion
            for prestacion in session.query(Prestacion)
            .filter(Prestacion.tenant_id == tenant.id)
            .all()
        }


def test_seed_crea_profesional_demo_vinculado_al_dueno(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    tenant = _tenant(app_env, session_factory)

    with session_factory() as session:
        dueno = session.query(Usuario).filter(Usuario.email == "dueno@demo").one()
        profesionales = session.query(Profesional).filter(Profesional.tenant_id == tenant.id).all()

    assert len(profesionales) == 1
    assert profesionales[0].usuario_id == dueno.id
    assert profesionales[0].nombre == "Profesional Demo"
    assert profesionales[0].activo is True


def test_seed_crea_exactamente_las_cinco_prestaciones(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    tenant = _tenant(app_env, session_factory)
    prestaciones = _prestaciones(session_factory, tenant)

    assert set(prestaciones) == set(PRESTACIONES_DEMO)
    assert {nombre: prestacion.duracion_min for nombre, prestacion in prestaciones.items()} == (
        PRESTACIONES_DEMO
    )
    assert all(prestacion.activa is True for prestacion in prestaciones.values())


def test_seed_no_duplica_filas_al_ejecutarse_dos_veces(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    tenant = _tenant(app_env, session_factory)
    profesionales_primera = _contar(session_factory, Profesional, tenant)
    prestaciones_primera = _contar(session_factory, Prestacion, tenant)

    segundo = run_seed()

    assert segundo["profesionales_creados"] == 0
    assert segundo["prestaciones_creadas"] == 0
    assert _contar(session_factory, Profesional, tenant) == profesionales_primera == 1
    assert _contar(session_factory, Prestacion, tenant) == prestaciones_primera == 5


def test_seed_sin_tabla_disponibilidad_no_falla_y_reporta_el_bloque_omitido(
    app_env: None, session_factory: sessionmaker[Session], db_engine: Engine
) -> None:
    resultado = run_seed()

    assert resultado["disponibilidad_omitida"] is True
    assert resultado["disponibilidad_creadas"] == 0
    with db_engine.connect() as conexion:
        existe = conexion.execute(
            text("SELECT to_regclass('public.disponibilidad') IS NOT NULL")
        ).scalar_one()
    assert existe is False


def test_seed_no_pisa_una_prestacion_existente_con_otro_precio(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    run_seed()
    with session_factory() as session:
        tenant = session.query(Tenant).filter(Tenant.slug == "demo").one()
        crear_prestacion(
            session,
            tenant,
            nombre="Consulta",
            duracion_min=30,
            precio_ref=Decimal("999.00"),
        )

    run_seed()

    prestaciones = _prestaciones(session_factory, tenant)
    assert len(prestaciones) == 5
    assert prestaciones["Consulta"].precio_ref == Decimal("999.00")
    assert prestaciones["Consulta"].duracion_min == 30


def test_seed_no_duplica_un_profesional_demo_ya_vinculado(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tenant = crear_tenant(session)
        dueno = crear_usuario(
            session, tenant, "dueno@demo", rol=RolUsuario.PROFESIONAL, es_dueno=True
        )
        crear_profesional(session, tenant, usuario=dueno, nombre="Profesional Existente")

    run_seed()

    with session_factory() as session:
        profesionales = session.query(Profesional).filter(Profesional.tenant_id == tenant.id).all()

    assert len(profesionales) == 1
    assert profesionales[0].nombre == "Profesional Existente"
    assert profesionales[0].usuario_id == dueno.id


def test_seed_con_tabla_disponibilidad_siembra_diez_filas_idempotentes(
    app_env: None, session_factory: sessionmaker[Session], db_engine: Engine
) -> None:
    with db_engine.begin() as conexion:
        conexion.execute(text(_DDL_DISPONIBILIDAD))

    primero = run_seed()
    segundo = run_seed()

    assert primero["disponibilidad_omitida"] is False
    assert primero["disponibilidad_creadas"] == 10
    assert segundo["disponibilidad_creadas"] == 0

    with db_engine.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT dia_semana, hora_desde, hora_hasta FROM disponibilidad "
                "ORDER BY dia_semana, hora_desde"
            )
        ).all()
    assert len(filas) == 10
    assert {fila[0] for fila in filas} == {0, 1, 2, 3, 4}
    assert {(str(fila[1]), str(fila[2])) for fila in filas} == {
        ("09:00:00", "13:00:00"),
        ("16:00:00", "20:00:00"),
    }


def _contar(session_factory: sessionmaker[Session], modelo: type, tenant: Tenant) -> int:
    with session_factory() as session:
        return session.query(modelo).filter(modelo.tenant_id == tenant.id).count()


def test_dos_corridas_dejan_exactamente_las_mismas_filas(
    app_env: None, session_factory: sessionmaker[Session], db_engine: Engine
) -> None:
    with db_engine.begin() as conexion:
        conexion.execute(text(_DDL_DISPONIBILIDAD))

    run_seed()
    with session_factory() as session:
        primera = _foto(session)
    with db_engine.connect() as conexion:
        disponibilidad_primera = conexion.execute(
            text("SELECT * FROM disponibilidad ORDER BY dia_semana, hora_desde")
        ).all()

    run_seed()
    with session_factory() as session:
        segunda = _foto(session)
    with db_engine.connect() as conexion:
        disponibilidad_segunda = conexion.execute(
            text("SELECT * FROM disponibilidad ORDER BY dia_semana, hora_desde")
        ).all()

    assert segunda == primera
    assert disponibilidad_segunda == disponibilidad_primera


def _foto(session: Session) -> dict[str, list[tuple[object, ...]]]:
    tenant = session.query(Tenant).filter(Tenant.slug == "demo").one()
    profesionales = (
        session.query(Profesional)
        .filter(Profesional.tenant_id == tenant.id)
        .order_by(Profesional.nombre)
        .all()
    )
    prestaciones = (
        session.query(Prestacion)
        .filter(Prestacion.tenant_id == tenant.id)
        .order_by(Prestacion.nombre)
        .all()
    )
    return {
        "profesionales": [
            (p.id, p.usuario_id, p.nombre, p.matricula, p.especialidad, p.activo)
            for p in profesionales
        ],
        "prestaciones": [
            (p.id, p.nombre, p.duracion_min, p.precio_ref, p.activa) for p in prestaciones
        ],
    }
