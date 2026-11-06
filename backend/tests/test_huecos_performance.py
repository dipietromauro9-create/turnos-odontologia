"""Performance, paginación por rango y determinismo del motor de huecos.

No agrega migración ni índice: verifica que las consultas del repositorio se
resuelvan con los índices ya existentes y mide contra PostgreSQL real.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as hora
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, select, text
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
from app.domain.huecos.service import enumerar_huecos
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2030, 6, 1, 8, tzinfo=TZ)
LUNES = date(2030, 6, 3)
DESDE = datetime.combine(LUNES, hora(0), TZ)
PRESUPUESTO_SEMANA = 1.0
PRESUPUESTO_DIA = 1.0
PRESUPUESTO_31_DIAS = 1.0

INDICE_TURNOS = "ix_turno_tenant_profesional_inicio"
INDICE_BLOQUEOS = "ix_bloqueo_tenant_profesional_desde"
INDICE_DISPONIBILIDAD = "ix_disponibilidad_tenant_profesional_dia"


@dataclass(frozen=True)
class EntornoPerformance:
    tenant: Tenant
    profesional: Profesional
    sin_agenda: Profesional
    prestacion: Prestacion
    paciente: Paciente


@pytest.fixture()
def entorno_performance(
    app_env: None, session_factory: sessionmaker[Session]
) -> Iterator[EntornoPerformance]:
    with session_factory() as session:
        tenant = crear_tenant(session)
        profesional = crear_profesional(session, tenant)
        sin_agenda = crear_profesional(session, tenant, nombre="Sin Agenda Ficticio")
        prestacion = crear_prestacion(session, tenant, duracion_min=30)
        paciente = Paciente(
            tenant_id=tenant.id,
            nombre="Paciente Ficticio",
            telefono="1145550001",
        )
        session.add(paciente)
        session.commit()
        _sembrar_semana(session, tenant, profesional, prestacion, paciente)
        session.execute(text("ANALYZE"))
        session.commit()
        resultado = EntornoPerformance(tenant, profesional, sin_agenda, prestacion, paciente)
    yield resultado


def _sembrar_semana(
    session: Session,
    tenant: Tenant,
    profesional: Profesional,
    prestacion: Prestacion,
    paciente: Paciente,
) -> None:
    """Semana representativa: dos bloques por día, ocupación y bloqueos."""
    for dia in range(7):
        session.add_all(
            [
                Disponibilidad(
                    tenant_id=tenant.id,
                    profesional_id=profesional.id,
                    dia_semana=dia,
                    hora_desde=hora(9),
                    hora_hasta=hora(12),
                ),
                Disponibilidad(
                    tenant_id=tenant.id,
                    profesional_id=profesional.id,
                    dia_semana=dia,
                    hora_desde=hora(14),
                    hora_hasta=hora(18),
                ),
            ]
        )

    codigo = 0

    def agregar_turno(
        fecha: date,
        inicio_hora: hora,
        fin_hora: hora,
        *,
        quien: Profesional,
        estado: EstadoTurno = EstadoTurno.RESERVADO,
    ) -> None:
        nonlocal codigo
        codigo += 1
        session.add(
            Turno(
                tenant_id=tenant.id,
                profesional_id=quien.id,
                paciente_id=paciente.id,
                prestacion_id=prestacion.id,
                inicio=datetime.combine(fecha, inicio_hora, TZ),
                fin=datetime.combine(fecha, fin_hora, TZ),
                estado=estado,
                codigo_publico=f"PERF{codigo:08d}",
            )
        )

    def agregar_slots(fecha: date, desde_hora: hora, cantidad: int) -> None:
        for tramo in range(cantidad):
            inicio_dt = datetime.combine(fecha, desde_hora, TZ) + timedelta(minutes=30 * tramo)
            agregar_turno(
                fecha,
                inicio_dt.time(),
                (inicio_dt + timedelta(minutes=30)).time(),
                quien=profesional,
            )

    agregar_slots(LUNES, hora(9), 6)
    agregar_slots(LUNES, hora(14), 8)

    for desplazamiento in range(1, 7):
        dia = LUNES + timedelta(days=desplazamiento)
        for inicio_hora, fin_hora in ((hora(9), hora(9, 30)), (hora(10), hora(10, 30))):
            agregar_turno(dia, inicio_hora, fin_hora, quien=profesional)
        agregar_turno(dia, hora(15), hora(15, 30), quien=profesional)

    ajenos = [
        crear_profesional(session, tenant, nombre=f"Otro Profesional {indice}")
        for indice in range(8)
    ]
    for desplazamiento in range(7):
        dia = LUNES + timedelta(days=desplazamiento)
        for ajeno in ajenos:
            for inicio_hora in (hora(9), hora(10), hora(15)):
                agregar_turno(
                    dia,
                    inicio_hora,
                    (datetime.combine(dia, inicio_hora) + timedelta(minutes=30)).time(),
                    quien=ajeno,
                )

    session.add_all(
        [
            Bloqueo(
                tenant_id=tenant.id,
                profesional_id=None,
                desde=datetime.combine(LUNES + timedelta(days=2), hora(16), TZ),
                hasta=datetime.combine(LUNES + timedelta(days=2), hora(17), TZ),
                motivo="Cierre global ficticio",
            ),
            Bloqueo(
                tenant_id=tenant.id,
                profesional_id=profesional.id,
                desde=datetime.combine(LUNES + timedelta(days=4), hora(10, 30), TZ),
                hasta=datetime.combine(LUNES + timedelta(days=4), hora(11), TZ),
                motivo="Cierre personal ficticio",
            ),
        ]
    )
    session.commit()


def _medir(
    entorno: EntornoPerformance, desde: datetime, hasta: datetime
) -> tuple[float, list[Any]]:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        enumerar_huecos(
            entorno.profesional.id,
            entorno.prestacion.id,
            desde,
            hasta,
            ahora=AHORA,
        )
        medidas = []
        for _ in range(3):
            inicio = time.perf_counter()
            huecos = enumerar_huecos(
                entorno.profesional.id,
                entorno.prestacion.id,
                desde,
                hasta,
                ahora=AHORA,
            )
            medidas.append(time.perf_counter() - inicio)
    return min(medidas), huecos


def test_una_semana_representativa_bajo_1_segundo(entorno_performance: EntornoPerformance) -> None:
    transcurrido, huecos = _medir(entorno_performance, DESDE, DESDE + timedelta(days=7))
    print(f"\nSEMANA: {transcurrido * 1000:.1f} ms, {len(huecos)} huecos")
    assert huecos
    assert transcurrido < PRESUPUESTO_SEMANA
    inicios = [h.inicio for h in huecos]
    assert inicios == sorted(inicios)
    assert len(inicios) == len(set(inicios))


def test_un_dia_denso_bajo_presupuesto(entorno_performance: EntornoPerformance) -> None:
    transcurrido, huecos = _medir(entorno_performance, DESDE, DESDE + timedelta(days=1))
    print(f"\nDIA DENSO: {transcurrido * 1000:.1f} ms, {len(huecos)} huecos")
    assert transcurrido < PRESUPUESTO_DIA
    assert isinstance(huecos, list)


def test_un_rango_de_31_dias_en_el_borde_permitido(
    entorno_performance: EntornoPerformance,
) -> None:
    transcurrido, huecos = _medir(entorno_performance, DESDE, DESDE + timedelta(days=31))
    print(f"\n31 DIAS: {transcurrido * 1000:.1f} ms, {len(huecos)} huecos")
    assert huecos
    assert transcurrido < PRESUPUESTO_31_DIAS
    assert [h.inicio for h in huecos] == sorted(h.inicio for h in huecos)


def test_rango_mayor_a_31_dias_se_rechaza_en_el_servicio(
    entorno_performance: EntornoPerformance,
) -> None:
    with (
        tenant_context(entorno_performance.tenant.id, entorno_performance.tenant.slug),
        pytest.raises(DomainError) as exc,
    ):
        enumerar_huecos(
            entorno_performance.profesional.id,
            entorno_performance.prestacion.id,
            DESDE,
            DESDE + timedelta(days=31, seconds=1),
            ahora=AHORA,
        )
    assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 422)
    assert exc.value.details == {"reason": "rango_invalido"}


def test_datos_vacios_responde_rapido_y_sin_huecos(
    entorno_performance: EntornoPerformance,
) -> None:
    with tenant_context(entorno_performance.tenant.id, entorno_performance.tenant.slug):
        inicio = time.perf_counter()
        huecos = enumerar_huecos(
            entorno_performance.sin_agenda.id,
            entorno_performance.prestacion.id,
            DESDE,
            DESDE + timedelta(days=7),
            ahora=AHORA,
        )
        transcurrido = time.perf_counter() - inicio
    print(f"\nSIN DATOS: {transcurrido * 1000:.1f} ms")
    assert huecos == []
    assert transcurrido < PRESUPUESTO_SEMANA


def test_consultas_repetidas_son_deterministas_y_no_por_candidato(
    entorno_performance: EntornoPerformance,
) -> None:
    consultas: list[str] = []

    def _contar(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        sentencia = statement.lstrip().upper()
        if sentencia.startswith("SELECT") and sentencia != "SELECT 1":
            consultas.append(statement)

    with tenant_context(entorno_performance.tenant.id, entorno_performance.tenant.slug):
        event.listen(Engine, "before_cursor_execute", _contar)
        try:
            primero = enumerar_huecos(
                entorno_performance.profesional.id,
                entorno_performance.prestacion.id,
                DESDE,
                DESDE + timedelta(days=7),
                ahora=AHORA,
            )
            segundo = enumerar_huecos(
                entorno_performance.profesional.id,
                entorno_performance.prestacion.id,
                DESDE,
                DESDE + timedelta(days=7),
                ahora=AHORA,
            )
        finally:
            event.remove(Engine, "before_cursor_execute", _contar)

    assert primero == segundo
    assert len(consultas) == 10


def _explicar(session: Session, consulta: Any) -> str:
    sql = str(consulta.compile(compile_kwargs={"literal_binds": True}))
    session.execute(text("SET LOCAL enable_seqscan = off"))
    session.execute(text("SET LOCAL enable_bitmapscan = off"))
    plan = session.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
    return json.dumps(plan)


def test_las_consultas_usan_los_indices_existentes(
    entorno_performance: EntornoPerformance, session_factory: sessionmaker[Session]
) -> None:
    entorno = entorno_performance
    with session_factory() as session:
        plan_franjas = _explicar(
            session,
            select(Disponibilidad)
            .where(
                Disponibilidad.tenant_id == entorno.tenant.id,
                Disponibilidad.profesional_id == entorno.profesional.id,
                Disponibilidad.dia_semana.in_(range(7)),
            )
            .order_by(Disponibilidad.dia_semana, Disponibilidad.hora_desde),
        )
        plan_bloqueos = _explicar(
            session,
            select(Bloqueo).where(
                Bloqueo.tenant_id == entorno.tenant.id,
                Bloqueo.profesional_id.in_([entorno.profesional.id, None]),
                Bloqueo.desde < DESDE + timedelta(days=7),
                Bloqueo.hasta > DESDE,
            ),
        )
        plan_turnos = _explicar(
            session,
            select(Turno).where(
                Turno.tenant_id == entorno.tenant.id,
                Turno.profesional_id == entorno.profesional.id,
                Turno.estado != EstadoTurno.CANCELADO,
                Turno.inicio < DESDE + timedelta(days=7),
                Turno.fin > DESDE,
            ),
        )

    with session_factory() as session:
        existentes = set(
            session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
                    "AND indexname IN (:turnos, :bloqueos, :disponibilidad)"
                ),
                {
                    "turnos": INDICE_TURNOS,
                    "bloqueos": INDICE_BLOQUEOS,
                    "disponibilidad": INDICE_DISPONIBILIDAD,
                },
            ).scalars()
        )

    print(f"\nPLAN FRANJAS: {plan_franjas}")
    print(f"\nPLAN BLOQUEOS: {plan_bloqueos}")
    print(f"\nPLAN TURNOS: {plan_turnos}")
    assert existentes == {INDICE_TURNOS, INDICE_BLOQUEOS, INDICE_DISPONIBILIDAD}
    assert "Seq Scan" not in plan_franjas and '"Index Name"' in plan_franjas
    assert INDICE_BLOQUEOS in plan_bloqueos
    assert INDICE_TURNOS in plan_turnos
