"""Fábricas de datos ficticios para tests (R9: nunca datos reales)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import RolUsuario, Tenant, Usuario

PASSWORD_FICTICIO = "$argon2id$v=19$m=65536,t=3,p=4$hash$ficticio"


def crear_tenant(
    session: Session,
    slug: str = "demo",
    nombre: str = "Consultorio Ficticio",
) -> Tenant:
    tenant = Tenant(slug=slug, nombre=nombre)
    session.add(tenant)
    session.commit()
    return tenant


def crear_usuario(
    session: Session,
    tenant: Tenant,
    email: str,
    rol: RolUsuario = RolUsuario.RECEPCION,
    *,
    es_dueno: bool = False,
    nombre: str = "Persona Ficticia",
) -> Usuario:
    usuario = Usuario(
        tenant_id=tenant.id,
        nombre=nombre,
        email=email,
        password_hash=PASSWORD_FICTICIO,
        rol=rol,
        es_dueno=es_dueno,
        activo=True,
    )
    session.add(usuario)
    session.commit()
    return usuario
