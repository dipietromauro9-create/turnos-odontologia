"""Persistencia real y última defensa anti-solape (RN-TU-01)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AuditMixin, EstadoTurno, Paciente, Tenant, TenantMixin, Turno
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration


def test_turno_metadata_frontera_referencias_fechas_e_indices() -> None:
    tabla = Turno.__table__
    assert issubclass(Turno, TenantMixin) and issubclass(Turno, AuditMixin)
    assert not tabla.c.tenant_id.nullable
    for campo, destino in (
        ("profesional_id", "profesional.id"),
        ("paciente_id", "paciente.id"),
        ("prestacion_id", "prestacion.id"),
    ):
        fk = next(iter(tabla.c[campo].foreign_keys))
        assert fk.target_fullname == destino and fk.ondelete == "RESTRICT"
    for campo in ("inicio", "fin", "creado_en", "actualizado_en"):
        assert isinstance(tabla.c[campo].type, DateTime) and tabla.c[campo].type.timezone
    assert tabla.c.codigo_publico.type.length == 12
    assert any(isinstance(c, ExcludeConstraint) for c in tabla.constraints)
    assert {tuple(i.columns.keys()) for i in tabla.indexes} >= {
        ("tenant_id", "profesional_id", "inicio"),
        ("tenant_id", "estado", "inicio"),
    }


def test_migracion_crea_turno_y_exclude_real(db_engine: Engine) -> None:
    assert inspect(db_engine).has_table("turno")
    with db_engine.connect() as conn:
        definicion = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ex_turno_profesional_no_solape'"
            )
        ).scalar_one()
    assert "tstzrange" in definicion and "cancelado" in definicion


def _referencias(session: Session, slug: str = "demo") -> dict[str, object]:
    tenant = crear_tenant(session, slug)
    profesional = crear_profesional(session, tenant)
    prestacion = crear_prestacion(session, tenant)
    paciente = Paciente(tenant_id=tenant.id, nombre="Paciente Ficticio", telefono="1145550001")
    session.add(paciente)
    session.commit()
    return dict(
        tenant_id=tenant.id,
        profesional_id=profesional.id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
    )


def _fila(refs: dict[str, object], **cambios: object) -> Turno:
    inicio = datetime(2030, 6, 3, 12, tzinfo=UTC)
    datos = dict(
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=EstadoTurno.RESERVADO,
        codigo_publico="abcdefgh1234",
        es_sobreturno=False,
    )
    datos.update(refs)
    datos.update(cambios)
    return Turno(**datos)


@pytest.mark.parametrize("estado", list(EstadoTurno))
def test_exclude_ocupa_todos_los_estados_salvo_cancelado(
    session_factory: sessionmaker[Session], estado: EstadoTurno
) -> None:
    with session_factory() as session:
        refs = _referencias(session)
        session.add(_fila(refs, estado=estado))
        session.commit()
        session.add(_fila(refs, codigo_publico="otroabcd1234"))
        if estado is EstadoTurno.CANCELADO:
            session.commit()
            assert session.query(Turno).count() == 2
        else:
            with pytest.raises(IntegrityError) as exc:
                session.commit()
            assert exc.value.orig.diag.constraint_name == "ex_turno_profesional_no_solape"


@pytest.mark.parametrize("caso", ["contiguo", "otro_profesional", "otro_tenant"])
def test_exclude_permite_adyacencia_y_agendas_independientes(
    session_factory: sessionmaker[Session], caso: str
) -> None:
    with session_factory() as session:
        refs = _referencias(session)
        primero = _fila(refs)
        session.add(primero)
        session.commit()
        otros = dict(refs)
        cambios: dict[str, object] = {"codigo_publico": "otroabcd1234"}
        if caso == "contiguo":
            cambios.update(inicio=primero.fin, fin=primero.fin + timedelta(minutes=30))
        elif caso == "otro_profesional":
            tenant = session.get(Tenant, refs["tenant_id"])
            otros["profesional_id"] = crear_profesional(session, tenant).id
        else:
            otros = _referencias(session, "otro")
        session.add(_fila(otros, **cambios))
        session.commit()
        assert session.query(Turno).count() == 2


@pytest.mark.parametrize(
    "cambios",
    [
        {"fin": datetime(2030, 6, 3, 12, tzinfo=UTC)},
        {"codigo_publico": "corto"},
        {"es_sobreturno": True},
        {"es_sobreturno": True, "motivo_sobreturno": "  "},
        {"motivo_sobreturno": "sin flag"},
        {"paciente_id": uuid.UUID(int=1)},
    ],
)
def test_constraints_rechazan_filas_invalidas(
    session_factory: sessionmaker[Session], cambios: dict[str, object]
) -> None:
    with session_factory() as session:
        refs = _referencias(session)
        session.add(_fila(refs, **cambios))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize("referencia", ["paciente_id", "profesional_id", "prestacion_id"])
def test_no_se_borra_fisicamente_el_catalogo_referido(
    session_factory: sessionmaker[Session], referencia: str
) -> None:
    from app.db.models import Prestacion, Profesional

    modelos = {"paciente_id": Paciente, "profesional_id": Profesional, "prestacion_id": Prestacion}
    with session_factory() as session:
        refs = _referencias(session)
        session.add(_fila(refs))
        session.commit()
        session.delete(session.get(modelos[referencia], refs[referencia]))
        with pytest.raises(IntegrityError):
            session.commit()


def test_upgrade_vacio_y_c06_y_downgrade_preservan_catalogos(
    db_url: str, db_engine: Engine
) -> None:
    from alembic import command
    from tests.test_pacientes_model import _alembic_config, _database_url

    config = _alembic_config(db_url)
    try:
        with _database_url(db_url):
            command.downgrade(config, "base")
            command.upgrade(config, "0005_disponibilidad_bloqueo")
        with Session(db_engine) as session:
            tenant_id = crear_tenant(session).id
        with _database_url(db_url):
            command.upgrade(config, "head")
        assert inspect(db_engine).has_table("turno")
        with _database_url(db_url):
            command.downgrade(config, "0005_disponibilidad_bloqueo")
        assert not inspect(db_engine).has_table("turno")
        assert inspect(db_engine).has_table("disponibilidad")
        with Session(db_engine) as session:
            assert session.get(Tenant, tenant_id) is not None
    finally:
        with _database_url(db_url):
            command.upgrade(config, "head")
    assert inspect(db_engine).has_table("turno")
