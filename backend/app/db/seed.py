"""Seed demo idempotente (R9: solo datos ficticios).

`python -m app.db.seed` crea el tenant `demo`, los usuarios `dueno@demo` /
`recepcion@demo`, el catálogo base y dos pacientes ficticios creados por el
dueño y tres turnos de ejemplo mediante el servicio. Si ya existen no los modifica
(no re-hashea, no pisa roles, fichas ni turnos). Los turnos nuevos que no cumplen
las reglas se omiten y se informan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from sqlalchemy import inspect, select, text

from app.core.errors import DomainError
from app.core.settings import get_settings
from app.db.models import (
    EstadoTurno,
    Paciente,
    Prestacion,
    Profesional,
    RolUsuario,
    Tenant,
    Turno,
    Usuario,
)
from app.db.session import get_engine, system_session, tenant_context, tenant_session
from app.domain.pacientes.telefono import normalizar_telefono
from app.domain.persistence import UnitOfWork
from app.domain.turnos.schemas import TurnoCreate
from app.domain.turnos.service import crear_ejemplo

DEMO_SLUG = "demo"
DEMO_NOMBRE = "Consultorio Demo"

PROFESIONAL_DEMO_NOMBRE = "Profesional Demo"

PRESTACIONES_DEMO: tuple[tuple[str, int], ...] = (
    ("Consulta", 30),
    ("Limpieza", 60),
    ("Extracción", 45),
    ("Control", 20),
    ("Urgencia", 30),
)

PACIENTES_DEMO: tuple[tuple[str, str], ...] = (
    ("Paciente Demo Uno", "1145550001"),
    ("Paciente Demo Dos", "1145550002"),
)

FRANJAS_DISPONIBILIDAD_DEMO: tuple[tuple[int, time, time], ...] = tuple(
    (dia, desde, hasta)
    for dia in range(5)
    for desde, hasta in ((time(9, 0), time(13, 0)), (time(16, 0), time(20, 0)))
)

_INSERT_DISPONIBILIDAD = text(
    """
    INSERT INTO disponibilidad
        (id, tenant_id, profesional_id, dia_semana, hora_desde, hora_hasta)
    SELECT :id, :tenant_id, :profesional_id, :dia_semana, :hora_desde, :hora_hasta
    WHERE NOT EXISTS (
        SELECT 1
        FROM disponibilidad
        WHERE tenant_id = :tenant_id
          AND profesional_id = :profesional_id
          AND dia_semana = :dia_semana
          AND hora_desde = :hora_desde
          AND hora_hasta = :hora_hasta
    )
    """
)

DEMO_PASSWORDS: dict[str, str] = {
    "dueno@demo": "demo-profesional-ficticio-2026",
    "recepcion@demo": "demo-recepcion-ficticio-2026",
}


@dataclass(frozen=True)
class _UsuarioDemo:
    email: str
    nombre: str
    rol: RolUsuario
    es_dueno: bool


DEMO_USERS: tuple[_UsuarioDemo, ...] = (
    _UsuarioDemo(
        email="dueno@demo",
        nombre="Profesional Demo",
        rol=RolUsuario.PROFESIONAL,
        es_dueno=True,
    ),
    _UsuarioDemo(
        email="recepcion@demo",
        nombre="Recepcion Demo",
        rol=RolUsuario.RECEPCION,
        es_dueno=False,
    ),
)


def _get_or_create_tenant() -> tuple[Tenant, bool]:
    with system_session() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == DEMO_SLUG)
        ).scalar_one_or_none()
        if tenant is not None:
            return tenant, False
        tenant = Tenant(slug=DEMO_SLUG, nombre=DEMO_NOMBRE)
        session.add(tenant)
        session.commit()
        return tenant, True


def _crear_usuarios_faltantes(tenant: Tenant) -> int:
    hasher = PasswordHasher()
    creados = 0
    with tenant_context(tenant.id, tenant.slug), UnitOfWork() as uow:
        repositorio = uow.repository(Usuario)
        existentes = {usuario.email for usuario in repositorio.list()}
        for demo in DEMO_USERS:
            if demo.email in existentes:
                continue
            repositorio.add(
                Usuario(
                    tenant_id=tenant.id,
                    nombre=demo.nombre,
                    email=demo.email,
                    password_hash=hasher.hash(DEMO_PASSWORDS[demo.email]),
                    rol=demo.rol,
                    es_dueno=demo.es_dueno,
                    activo=True,
                )
            )
            creados += 1
    return creados


def _sembrar_catalogo(tenant: Tenant) -> dict[str, Any]:
    """Get-or-create del profesional demo y de las prestaciones base (sin pisar)."""
    with tenant_context(tenant.id, tenant.slug), UnitOfWork() as uow:
        usuarios = uow.repository(Usuario).list(email=DEMO_USERS[0].email)
        if not usuarios:
            return {"profesionales_creados": 0, "prestaciones_creadas": 0, "profesional_id": None}
        dueno = usuarios[0]

        profesionales = uow.repository(Profesional)
        vinculados = profesionales.list(usuario_id=dueno.id)
        if vinculados:
            profesional = vinculados[0]
            profesionales_creados = 0
        else:
            profesional = profesionales.add(
                Profesional(nombre=PROFESIONAL_DEMO_NOMBRE, usuario_id=dueno.id, activo=True)
            )
            profesionales_creados = 1

        prestaciones = uow.repository(Prestacion)
        existentes = {prestacion.nombre for prestacion in prestaciones.list()}
        prestaciones_creadas = 0
        for nombre, duracion_min in PRESTACIONES_DEMO:
            if nombre in existentes:
                continue
            prestaciones.add(Prestacion(nombre=nombre, duracion_min=duracion_min, activa=True))
            prestaciones_creadas += 1

        return {
            "profesionales_creados": profesionales_creados,
            "prestaciones_creadas": prestaciones_creadas,
            "profesional_id": profesional.id,
            "dueno_id": dueno.id,
        }


def _crear_pacientes_faltantes(tenant: Tenant, dueno_id: uuid.UUID | None) -> int:
    """Crea los dos pacientes demo si falta su teléfono normalizado (R9)."""
    if not inspect(get_engine()).has_table("paciente"):
        return 0
    creados = 0
    with tenant_context(tenant.id, tenant.slug), tenant_session(tenant.id) as session:
        existentes = set(session.execute(select(Paciente.telefono)).scalars().all())
        for nombre, telefono in PACIENTES_DEMO:
            normalizado = normalizar_telefono(telefono)
            if normalizado in existentes:
                continue
            session.add(
                Paciente(
                    tenant_id=tenant.id,
                    nombre=nombre,
                    telefono=normalizado,
                    creado_por_usuario_id=dueno_id,
                )
            )
            creados += 1
        session.commit()
    return creados


def _sembrar_disponibilidad_demo(
    tenant: Tenant, profesional_id: uuid.UUID | None
) -> dict[str, Any]:
    """Siembra la plantilla Lun–Vie 9–13/16–20 solo si C-06 ya creó la tabla."""
    if profesional_id is None or not inspect(get_engine()).has_table("disponibilidad"):
        return {"disponibilidad_creadas": 0, "disponibilidad_omitida": True}

    creadas = 0
    with get_engine().begin() as conexion:
        for dia_semana, hora_desde, hora_hasta in FRANJAS_DISPONIBILIDAD_DEMO:
            resultado = conexion.execute(
                _INSERT_DISPONIBILIDAD,
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant.id,
                    "profesional_id": profesional_id,
                    "dia_semana": dia_semana,
                    "hora_desde": hora_desde,
                    "hora_hasta": hora_hasta,
                },
            )
            creadas += resultado.rowcount or 0

    return {"disponibilidad_creadas": creadas, "disponibilidad_omitida": False}


def _sembrar_turnos_demo(
    tenant: Tenant, profesional_id: uuid.UUID | None, dueno_id: uuid.UUID | None
) -> dict[str, int]:
    """Tres ejemplos persistidos por el servicio; nunca reabre ni mueve los existentes."""
    inspector = inspect(get_engine())
    if not inspector.has_table("turno") or not inspector.has_table("disponibilidad"):
        return {"turnos_creados": 0, "turnos_omitidos": 3}
    ids = [uuid.uuid5(tenant.id, f"C07-demo-{indice}") for indice in range(3)]
    with tenant_session(tenant.id) as session:
        existentes = set(
            session.execute(
                select(Turno.id).where(Turno.tenant_id == tenant.id, Turno.id.in_(ids))
            ).scalars()
        )
        profesional = session.get(Profesional, profesional_id) if profesional_id else None
        dueno = session.get(Usuario, dueno_id) if dueno_id else None
        # El catálogo permite nombres repetidos: elegir una candidata estable,
        # preferentemente activa, sin imponer unicidad nueva al usuario.
        prestacion = (
            session.execute(
                select(Prestacion)
                .where(Prestacion.tenant_id == tenant.id, Prestacion.nombre == "Consulta")
                .order_by(Prestacion.activa.desc(), Prestacion.creado_en, Prestacion.id)
                .limit(1)
            )
            .scalars()
            .first()
        )
        pacientes = list(
            session.execute(
                select(Paciente)
                .where(
                    Paciente.tenant_id == tenant.id,
                    Paciente.telefono.in_([telefono for _, telefono in PACIENTES_DEMO]),
                )
                .order_by(Paciente.telefono)
            ).scalars()
        )
    if (
        profesional is None
        or not profesional.activo
        or dueno is None
        or not dueno.activo
        or prestacion is None
        or not prestacion.activa
        or not pacientes
    ):
        return {"turnos_creados": 0, "turnos_omitidos": len(set(ids) - existentes)}
    ahora = datetime.now(ZoneInfo(get_settings().tz))
    dia = ahora.date() + timedelta(days=1)
    while dia.weekday() > 4:
        dia += timedelta(days=1)
    primero = datetime.combine(dia, time(9), ahora.tzinfo)
    creados, omitidos = 0, 0
    destinos = (EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO, EstadoTurno.ATENDIDO)
    for indice, destino in enumerate(destinos):
        if ids[indice] in existentes:
            continue
        datos = TurnoCreate(
            profesional_id=profesional.id,
            prestacion_id=prestacion.id,
            paciente_id=pacientes[indice % len(pacientes)].id,
            inicio=primero + timedelta(minutes=indice * prestacion.duracion_min),
        )
        try:
            with tenant_context(tenant.id, tenant.slug):
                resultado = crear_ejemplo(ids[indice], datos, dueno, destino, ahora=ahora)
            creados += int(resultado.creado)
        except DomainError as exc:
            if exc.code not in {"RN-AG-01", "RN-AG-02", "RN-TU-01", "RN-TU-02", "RN-AU-03"}:
                raise
            omitidos += 1
    return {"turnos_creados": creados, "turnos_omitidos": omitidos}


def run_seed() -> dict[str, Any]:
    tenant, tenant_creado = _get_or_create_tenant()
    usuarios_creados = _crear_usuarios_faltantes(tenant)
    catalogo = _sembrar_catalogo(tenant)
    profesional_id, dueno_id = catalogo.pop("profesional_id"), catalogo.pop("dueno_id")
    disponibilidad = _sembrar_disponibilidad_demo(tenant, profesional_id)
    pacientes_creados = _crear_pacientes_faltantes(tenant, dueno_id)
    turnos = _sembrar_turnos_demo(tenant, profesional_id, dueno_id)
    return {
        "tenant": tenant.slug,
        "tenant_creado": tenant_creado,
        "usuarios_creados": usuarios_creados,
        **catalogo,
        "pacientes_creados": pacientes_creados,
        **disponibilidad,
        **turnos,
    }


def main() -> int:
    resultado = run_seed()
    mensaje = (
        f"[seed] tenant={resultado['tenant']} "
        f"tenant_creado={resultado['tenant_creado']} "
        f"usuarios_creados={resultado['usuarios_creados']} "
        f"profesionales_creados={resultado['profesionales_creados']} "
        f"prestaciones_creadas={resultado['prestaciones_creadas']} "
        f"pacientes_creados={resultado['pacientes_creados']} "
        f"disponibilidad_creadas={resultado['disponibilidad_creadas']}"
        f" turnos_creados={resultado['turnos_creados']}"
        f" turnos_omitidos={resultado['turnos_omitidos']}"
    )
    if resultado["disponibilidad_omitida"]:
        mensaje += " disponibilidad=omitida (tabla ausente)"
    print(mensaje, flush=True)  # noqa: T201 - salida operativa del seed
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
