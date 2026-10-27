"""Seed demo idempotente (R9: solo datos ficticios, sin pacientes).

`python -m app.db.seed` crea el tenant `demo` y los usuarios `dueno@demo` /
`recepcion@demo`. Si ya existen no los modifica (no re-hashea ni pisa roles).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import select

from app.db.models import RolUsuario, Tenant, Usuario
from app.db.session import system_session, tenant_context
from app.domain.persistence import UnitOfWork

DEMO_SLUG = "demo"
DEMO_NOMBRE = "Consultorio Demo"

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


def run_seed() -> dict[str, Any]:
    tenant, tenant_creado = _get_or_create_tenant()
    usuarios_creados = _crear_usuarios_faltantes(tenant)
    return {
        "tenant": tenant.slug,
        "tenant_creado": tenant_creado,
        "usuarios_creados": usuarios_creados,
    }


def main() -> int:
    resultado = run_seed()
    mensaje = (
        f"[seed] tenant={resultado['tenant']} "
        f"tenant_creado={resultado['tenant_creado']} "
        f"usuarios_creados={resultado['usuarios_creados']}"
    )
    print(mensaje, flush=True)  # noqa: T201 - salida operativa del seed
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
