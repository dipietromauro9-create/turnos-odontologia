"""Adapta el alcance RBAC existente al vínculo Usuario → Profesional de agenda."""

import uuid

from sqlalchemy import select

from app.core.errors import DomainError
from app.db.models import Profesional, Usuario
from app.db.session import TenantSession
from app.domain.auth.dependencies import AlcanceAgenda, alcance_agenda


def profesional_de_usuario(session: TenantSession, usuario: Usuario) -> Profesional:
    propio = session.execute(
        select(Profesional).where(Profesional.usuario_id == usuario.id)
    ).scalar_one_or_none()
    if propio is None:
        raise DomainError(
            "RN-AU-03",
            "El usuario no tiene profesional vinculado",
            403,
            details={"reason": "profesional_no_vinculado"},
        )
    return propio


def profesional_del_alcance(
    session: TenantSession, usuario: Usuario, solicitado: uuid.UUID | None
) -> uuid.UUID | None:
    if alcance_agenda(usuario) is AlcanceAgenda.TODAS:
        return solicitado
    propio = profesional_de_usuario(session, usuario)
    if solicitado is not None and solicitado != propio.id:
        raise DomainError(
            "RN-AU-03",
            "Solo puede consultar su propia agenda",
            403,
            details={"reason": "fuera_de_alcance"},
        )
    return propio.id
