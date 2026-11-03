"""Fábricas de datos ficticios para tests (R9: nunca datos reales)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Prestacion,
    Profesional,
    RolUsuario,
    Tenant,
    Usuario,
)

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


def crear_usuario_con_password(
    session: Session,
    tenant: Tenant,
    email: str,
    password: str,
    rol: RolUsuario = RolUsuario.RECEPCION,
    *,
    es_dueno: bool = False,
    nombre: str = "Persona Ficticia",
) -> Usuario:
    """Crea un usuario con un hash Argon2id real (verificable con `verify_password`)."""
    usuario = Usuario(
        tenant_id=tenant.id,
        nombre=nombre,
        email=email,
        password_hash=hash_password(password),
        rol=rol,
        es_dueno=es_dueno,
        activo=True,
    )
    session.add(usuario)
    session.commit()
    return usuario


def crear_profesional(
    session: Session,
    tenant: Tenant,
    *,
    usuario: Usuario | None = None,
    nombre: str = "Profesional Ficticio",
    matricula: str | None = None,
    especialidad: str | None = None,
    activo: bool = True,
) -> Profesional:
    """Profesional ficticio, opcionalmente vinculado a un usuario de login (R9)."""
    profesional = Profesional(
        tenant_id=tenant.id,
        usuario_id=usuario.id if usuario is not None else None,
        nombre=nombre,
        matricula=matricula,
        especialidad=especialidad,
        activo=activo,
    )
    session.add(profesional)
    session.commit()
    return profesional


def crear_prestacion(
    session: Session,
    tenant: Tenant,
    *,
    nombre: str = "Prestación Ficticia",
    duracion_min: int = 30,
    precio_ref: Decimal | None = None,
    activa: bool = True,
) -> Prestacion:
    """Prestación ficticia con duración válida (positiva y múltiplo de 5)."""
    prestacion = Prestacion(
        tenant_id=tenant.id,
        nombre=nombre,
        duracion_min=duracion_min,
        precio_ref=precio_ref,
        activa=activa,
    )
    session.add(prestacion)
    session.commit()
    return prestacion
