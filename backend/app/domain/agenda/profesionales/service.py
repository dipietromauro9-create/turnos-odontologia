"""Servicio del directorio de profesionales: vínculo con usuario y persistencia."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.db.models import Profesional, RolUsuario, Usuario
from app.domain.agenda.profesionales.schemas import ProfesionalCreate, ProfesionalUpdate
from app.domain.persistence import UnitOfWork

RN_GL_01 = "RN-GL-01"


def _no_encontrado(recurso: str = "profesional") -> DomainError:
    return DomainError(
        RN_GL_01,
        f"El/la {recurso} no existe",
        status_code=404,
        details={"reason": "no_encontrado"},
    )


def _usuario_no_vinculable() -> DomainError:
    return DomainError(
        RN_GL_01,
        "El usuario no puede vincularse a un profesional",
        status_code=422,
        details={"reason": "usuario_no_vinculable"},
    )


def _usuario_ya_vinculado() -> DomainError:
    return DomainError(
        RN_GL_01,
        "El usuario ya está vinculado a otro profesional",
        status_code=409,
        details={"reason": "usuario_ya_vinculado"},
    )


def validar_usuario_vinculable(usuario: Usuario | None) -> Usuario:
    """Función pura: existe en el tenant y tiene rol profesional."""
    if usuario is None:
        raise _no_encontrado("usuario")
    if usuario.rol != RolUsuario.PROFESIONAL:
        raise _usuario_no_vinculable()
    return usuario


def resolver_usuario_vinculable(uow: UnitOfWork, usuario_id: uuid.UUID) -> Usuario:
    """Resuelve el usuario con la sesión tenant-scoped y valida que sea vinculable."""
    return validar_usuario_vinculable(uow.repository(Usuario).get(usuario_id))


def validar_vinculo_libre(
    vinculados: list[Profesional], *, excluir_id: uuid.UUID | None = None
) -> None:
    """Función pura: ningún otro profesional puede tener el mismo usuario."""
    if any(profesional.id != excluir_id for profesional in vinculados):
        raise _usuario_ya_vinculado()


def _refrescar(uow: UnitOfWork, profesional: Profesional) -> None:
    """Trae los defaults del servidor antes de cerrar la sesión (objeto desacoplado)."""
    uow.session.refresh(profesional)


def _validar_cambios(cambios: dict[str, Any]) -> None:
    if "nombre" in cambios and cambios["nombre"] is None:
        raise DomainError(
            RN_GL_01,
            "El nombre no puede estar vacío",
            status_code=422,
            details={"reason": "nombre_invalido"},
        )


def listar(*, activo: bool | None = None) -> list[Profesional]:
    with UnitOfWork() as uow:
        filtros: dict[str, Any] = {} if activo is None else {"activo": activo}
        profesionales = uow.repository(Profesional).list(**filtros)
        return sorted(profesionales, key=lambda profesional: profesional.nombre)


def obtener(profesional_id: uuid.UUID) -> Profesional:
    with UnitOfWork() as uow:
        profesional = uow.repository(Profesional).get(profesional_id)
        if profesional is None:
            raise _no_encontrado()
        return profesional


def crear(datos: ProfesionalCreate) -> Profesional:
    with UnitOfWork() as uow:
        profesionales = uow.repository(Profesional)
        if datos.usuario_id is not None:
            resolver_usuario_vinculable(uow, datos.usuario_id)
            validar_vinculo_libre(profesionales.list(usuario_id=datos.usuario_id))
        try:
            profesional = profesionales.add(
                Profesional(
                    nombre=datos.nombre,
                    usuario_id=datos.usuario_id,
                    matricula=datos.matricula,
                    especialidad=datos.especialidad,
                    activo=datos.activo,
                )
            )
        except IntegrityError as exc:
            uow.session.rollback()
            raise _usuario_ya_vinculado() from exc
        _refrescar(uow, profesional)
        return profesional


def actualizar(profesional_id: uuid.UUID, datos: ProfesionalUpdate) -> Profesional:
    cambios = datos.model_dump(exclude_unset=True)
    _validar_cambios(cambios)
    with UnitOfWork() as uow:
        profesionales = uow.repository(Profesional)
        if profesionales.get(profesional_id) is None:
            raise _no_encontrado()
        if cambios.get("usuario_id") is not None:
            resolver_usuario_vinculable(uow, cambios["usuario_id"])
            validar_vinculo_libre(
                profesionales.list(usuario_id=cambios["usuario_id"]),
                excluir_id=profesional_id,
            )
        try:
            profesional = profesionales.update(profesional_id, **cambios)
        except IntegrityError as exc:
            uow.session.rollback()
            raise _usuario_ya_vinculado() from exc
        if profesional is None:
            raise _no_encontrado()
        _refrescar(uow, profesional)
        return profesional


__all__ = [
    "actualizar",
    "crear",
    "listar",
    "obtener",
    "resolver_usuario_vinculable",
    "validar_usuario_vinculable",
    "validar_vinculo_libre",
]
