"""Repositorio y servicio de huecos contra PostgreSQL real (R3: tenant explícito)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import (
    Bloqueo,
    Disponibilidad,
    EstadoTurno,
    Paciente,
    Prestacion,
    Profesional,
    Tenant,
    Turno,
)
from app.db.session import tenant_context
from app.domain.huecos.repository import HuecosRepository
from app.domain.huecos.service import enumerar_huecos
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2030, 6, 1, 8, tzinfo=TZ)  # sábado previo al lunes consultado
LUNES = date(2030, 6, 3)
MARTES = LUNES + timedelta(days=1)
DESDE = datetime.combine(LUNES, time(0), TZ)
HASTA = datetime.combine(MARTES, time(0), TZ)


@dataclass(frozen=True)
class EntornoHuecos:
    tenant: Tenant
    otro_tenant: Tenant
    profesional: Profesional
    segundo: Profesional
    ajeno: Profesional
    prestacion: Prestacion
    prestacion_45: Prestacion
    prestacion_ajena: Prestacion
    paciente: Paciente
    paciente_ajeno: Paciente


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[EntornoHuecos]:
    with session_factory() as session:
        tenant = crear_tenant(session, "demo")
        otro_tenant = crear_tenant(session, "otro")
        profesional = crear_profesional(session, tenant)
        segundo = crear_profesional(session, tenant, nombre="Segundo Ficticio")
        ajeno = crear_profesional(session, otro_tenant, nombre="Ajeno Ficticio")
        prestacion = crear_prestacion(session, tenant, duracion_min=30)
        prestacion_45 = crear_prestacion(
            session, tenant, nombre="Prestación Larga Ficticia", duracion_min=45
        )
        prestacion_ajena = crear_prestacion(session, otro_tenant, nombre="Ajena Ficticia")
        paciente = Paciente(
            tenant_id=tenant.id,
            nombre="Paciente Ficticio",
            telefono="1145550001",
        )
        paciente_ajeno = Paciente(
            tenant_id=otro_tenant.id,
            nombre="Paciente Ajeno Ficticio",
            telefono="1145550002",
        )
        session.add_all([paciente, paciente_ajeno])
        session.add(
            Disponibilidad(
                tenant_id=tenant.id,
                profesional_id=profesional.id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(12),
            )
        )
        session.commit()
        yield EntornoHuecos(
            tenant,
            otro_tenant,
            profesional,
            segundo,
            ajeno,
            prestacion,
            prestacion_45,
            prestacion_ajena,
            paciente,
            paciente_ajeno,
        )


@contextmanager
def _repo(tenant: Tenant) -> Iterator[HuecosRepository]:
    from app.domain.persistence import UnitOfWork

    with tenant_context(tenant.id, tenant.slug), UnitOfWork() as uow:
        yield HuecosRepository(uow.session)


def _agregar_bloqueo(
    session: Session,
    tenant: Tenant,
    *,
    profesional_id: uuid.UUID | None,
    desde: datetime,
    hasta: datetime,
) -> Bloqueo:
    fila = Bloqueo(
        tenant_id=tenant.id,
        profesional_id=profesional_id,
        desde=desde,
        hasta=hasta,
        motivo="Cierre ficticio",
    )
    session.add(fila)
    session.commit()
    return fila


def _agregar_turno(
    session: Session,
    entorno: EntornoHuecos,
    *,
    inicio: datetime,
    fin: datetime,
    estado: EstadoTurno = EstadoTurno.RESERVADO,
    codigo: str = "COD000000001",
    tenant: Tenant | None = None,
    profesional: Profesional | None = None,
    paciente: Paciente | None = None,
) -> Turno:
    tenant = tenant or entorno.tenant
    fila = Turno(
        tenant_id=tenant.id,
        profesional_id=(profesional or entorno.profesional).id,
        paciente_id=(paciente or entorno.paciente).id,
        prestacion_id=entorno.prestacion.id,
        inicio=inicio,
        fin=fin,
        estado=estado,
        codigo_publico=codigo,
    )
    session.add(fila)
    session.commit()
    return fila


# --- Grupo 4: repositorio ---


def test_franjas_filtra_por_dias_del_rango(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        session.add(
            Disponibilidad(
                tenant_id=entorno.tenant.id,
                profesional_id=entorno.profesional.id,
                dia_semana=1,
                hora_desde=time(10),
                hora_hasta=time(11),
            )
        )
        session.commit()

    with _repo(entorno.tenant) as repo:
        assert [f.dia_semana for f in repo.franjas(entorno.profesional.id, {0})] == [0]
        assert [f.dia_semana for f in repo.franjas(entorno.profesional.id, {1})] == [1]
        assert [f.dia_semana for f in repo.franjas(entorno.profesional.id, {0, 1})] == [0, 1]


def test_bloqueos_incluye_propios_y_globales_y_excluye_ajenos(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        propio = _agregar_bloqueo(
            session,
            entorno.tenant,
            profesional_id=entorno.profesional.id,
            desde=datetime.combine(LUNES, time(10), TZ),
            hasta=datetime.combine(LUNES, time(11), TZ),
        )
        global_ = _agregar_bloqueo(
            session,
            entorno.tenant,
            profesional_id=None,
            desde=datetime.combine(LUNES, time(9), TZ),
            hasta=datetime.combine(LUNES, time(10), TZ),
        )
        _agregar_bloqueo(
            session,
            entorno.tenant,
            profesional_id=entorno.segundo.id,
            desde=datetime.combine(LUNES, time(11), TZ),
            hasta=datetime.combine(LUNES, time(12), TZ),
        )
        _agregar_bloqueo(
            session,
            entorno.tenant,
            profesional_id=entorno.profesional.id,
            desde=datetime.combine(MARTES, time(9), TZ),
            hasta=datetime.combine(MARTES, time(10), TZ),
        )

    with _repo(entorno.tenant) as repo:
        filas = repo.bloqueos(entorno.profesional.id, DESDE, HASTA)
        assert {fila.id for fila in filas} == {propio.id, global_.id}


def test_turnos_excluye_cancelados_y_fuera_de_rango(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        esperados = []
        for indice, estado in enumerate(
            [
                EstadoTurno.RESERVADO,
                EstadoTurno.CONFIRMADO,
                EstadoTurno.ATENDIDO,
                EstadoTurno.AUSENTE,
            ]
        ):
            inicio = datetime.combine(LUNES, time(9), TZ) + timedelta(minutes=30 * indice)
            esperados.append(
                _agregar_turno(
                    session,
                    entorno,
                    inicio=inicio,
                    fin=inicio + timedelta(minutes=30),
                    estado=estado,
                    codigo=f"COD{indice:09d}",
                ).id
            )
        _agregar_turno(
            session,
            entorno,
            inicio=datetime.combine(LUNES, time(11), TZ),
            fin=datetime.combine(LUNES, time(11, 30), TZ),
            estado=EstadoTurno.CANCELADO,
            codigo="COD000000009",
        )
        _agregar_turno(
            session,
            entorno,
            inicio=datetime.combine(MARTES, time(9), TZ),
            fin=datetime.combine(MARTES, time(9, 30), TZ),
            codigo="COD000000010",
        )

    with _repo(entorno.tenant) as repo:
        filas = repo.turnos(entorno.profesional.id, DESDE, HASTA)
        assert {fila.id for fila in filas} == set(esperados)


def test_el_tenant_a_no_ve_datos_del_tenant_b(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        _agregar_bloqueo(
            session,
            entorno.otro_tenant,
            profesional_id=None,
            desde=datetime.combine(LUNES, time(9), TZ),
            hasta=datetime.combine(LUNES, time(12), TZ),
        )
        session.add(
            Disponibilidad(
                tenant_id=entorno.otro_tenant.id,
                profesional_id=entorno.ajeno.id,
                dia_semana=0,
                hora_desde=time(9),
                hora_hasta=time(12),
            )
        )
        session.commit()

    with _repo(entorno.tenant) as repo:
        assert repo.obtener_profesional(entorno.ajeno.id) is None
        assert repo.obtener_prestacion(entorno.prestacion_ajena.id) is None
        assert repo.bloqueos(entorno.profesional.id, DESDE, HASTA) == []
        assert repo.franjas(entorno.ajeno.id, {0}) == []


# --- Grupo 4: servicio ---


def test_enumerar_huecos_aplica_la_grilla(entorno: EntornoHuecos) -> None:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        huecos = enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            DESDE,
            HASTA,
            ahora=AHORA,
        )
    assert [(h.inicio.hour, h.inicio.minute) for h in huecos] == [
        (9, 0),
        (9, 30),
        (10, 0),
        (10, 30),
        (11, 0),
        (11, 30),
    ]
    assert all(h.fin - h.inicio == timedelta(minutes=30) for h in huecos)


def test_enumerar_huecos_excluye_bloqueos_y_turnos(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        _agregar_bloqueo(
            session,
            entorno.tenant,
            profesional_id=entorno.profesional.id,
            desde=datetime.combine(LUNES, time(9, 30), TZ),
            hasta=datetime.combine(LUNES, time(10), TZ),
        )
        _agregar_turno(
            session,
            entorno,
            inicio=datetime.combine(LUNES, time(10, 30), TZ),
            fin=datetime.combine(LUNES, time(11), TZ),
        )

    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        huecos = enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            DESDE,
            HASTA,
            ahora=AHORA,
        )
    assert [(h.inicio.hour, h.inicio.minute) for h in huecos] == [
        (9, 0),
        (10, 0),
        (11, 0),
        (11, 30),
    ]


@pytest.mark.parametrize("cual", ["profesional", "prestacion"])
def test_referencia_inexistente_es_404(entorno: EntornoHuecos, cual: str) -> None:
    profesional_id = uuid.uuid4() if cual == "profesional" else entorno.profesional.id
    prestacion_id = uuid.uuid4() if cual == "prestacion" else entorno.prestacion.id
    with tenant_context(entorno.tenant.id, entorno.tenant.slug), pytest.raises(DomainError) as exc:
        enumerar_huecos(profesional_id, prestacion_id, DESDE, HASTA, ahora=AHORA)
    assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 404)
    assert exc.value.details == {"reason": "no_encontrado"}


def test_referencia_de_otro_tenant_es_404(entorno: EntornoHuecos) -> None:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        with pytest.raises(DomainError) as exc:
            enumerar_huecos(
                entorno.ajeno.id,
                entorno.prestacion.id,
                DESDE,
                HASTA,
                ahora=AHORA,
            )
        assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 404)
        with pytest.raises(DomainError) as exc:
            enumerar_huecos(
                entorno.profesional.id,
                entorno.prestacion_ajena.id,
                DESDE,
                HASTA,
                ahora=AHORA,
            )
        assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 404)


@pytest.mark.parametrize("cual", ["profesional", "prestacion"])
def test_referencia_inactiva_es_422(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session], cual: str
) -> None:
    with session_factory() as session:
        if cual == "profesional":
            session.get(Profesional, entorno.profesional.id).activo = False
        else:
            session.get(Prestacion, entorno.prestacion.id).activa = False
        session.commit()

    with tenant_context(entorno.tenant.id, entorno.tenant.slug), pytest.raises(DomainError) as exc:
        enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            DESDE,
            HASTA,
            ahora=AHORA,
        )
    assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 422)
    assert exc.value.details == {"reason": "referencia_inactiva"}


def test_agenda_sin_franjas_devuelve_lista_vacia(entorno: EntornoHuecos) -> None:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        huecos = enumerar_huecos(
            entorno.segundo.id,
            entorno.prestacion.id,
            DESDE,
            HASTA,
            ahora=AHORA,
        )
    assert huecos == []


def test_rango_de_varias_semanas_enumera_cada_lunes(entorno: EntornoHuecos) -> None:
    hasta = datetime.combine(LUNES + timedelta(days=21), time(0), TZ)
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        huecos = enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            DESDE,
            hasta,
            ahora=AHORA,
        )
    assert len(huecos) == 18
    assert {h.inicio.date() for h in huecos} == {
        LUNES,
        LUNES + timedelta(days=7),
        LUNES + timedelta(days=14),
    }


def test_la_consulta_convierte_utc_a_la_zona_del_consultorio(entorno: EntornoHuecos) -> None:
    desde_utc = datetime(2030, 6, 3, 12, 0, tzinfo=UTC)  # 09:00 en Buenos Aires
    hasta_utc = datetime(2030, 6, 3, 15, 0, tzinfo=UTC)  # 12:00 en Buenos Aires
    ahora_utc = datetime(2030, 6, 1, 11, 0, tzinfo=UTC)  # 08:00 en Buenos Aires
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        huecos = enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            desde_utc,
            hasta_utc,
            ahora=ahora_utc,
        )
    assert len(huecos) == 6
    assert huecos[0].inicio == datetime.combine(LUNES, time(9), TZ)
    assert huecos[-1].fin == datetime.combine(LUNES, time(12), TZ)


def test_no_hay_consultas_por_hueco_candidato(entorno: EntornoHuecos) -> None:
    consultas: list[str] = []

    def _contar(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            consultas.append(statement)

    event.listen(Engine, "before_cursor_execute", _contar)
    try:
        with tenant_context(entorno.tenant.id, entorno.tenant.slug):
            huecos = enumerar_huecos(
                entorno.profesional.id,
                entorno.prestacion.id,
                DESDE,
                HASTA,
                ahora=AHORA,
            )
    finally:
        event.remove(Engine, "before_cursor_execute", _contar)

    assert len(huecos) == 6
    assert len(consultas) == 5


def test_enumerar_huecos_no_escribe_turnos(
    entorno: EntornoHuecos, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        _agregar_turno(
            session,
            entorno,
            inicio=datetime.combine(LUNES, time(9), TZ),
            fin=datetime.combine(LUNES, time(9, 30), TZ),
        )
        antes = session.query(Turno).count()

    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            DESDE,
            HASTA,
            ahora=AHORA,
        )

    with session_factory() as session:
        assert session.query(Turno).count() == antes
