"""Dependencias de auth: store efímero, sesión tenant-scoped y usuario actual.

El middleware valida el token sin base; acá se recarga la fila `Usuario` del
tenant resuelto porque rol, `es_dueno` y `activo` son la autoridad (R3).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.errors import DomainError
from app.core.token_store import RedisTokenStore, TokenStore
from app.db.models import RolUsuario, Usuario
from app.db.session import TenantSession, get_session, require_tenant
from app.domain.auth.middleware import current_principal

RN_AU_02 = "RN-AU-02"
RN_AU_03 = "RN-AU-03"


class AlcanceAgenda(StrEnum):
    """Qué agendas puede ver un usuario: todas las del consultorio o solo la propia."""

    TODAS = "todas"
    PROPIA = "propia"


@lru_cache(maxsize=1)
def _store_singleton() -> TokenStore:
    return RedisTokenStore()


def get_token_store() -> TokenStore:
    """Store de runtime (Redis); los tests lo sustituyen por uno en memoria."""
    return _store_singleton()


TokenStoreDep = Annotated[TokenStore, Depends(get_token_store)]
DbSessionDep = Annotated[TenantSession, Depends(get_session)]


def _sin_sesion(motivo: str) -> DomainError:
    return DomainError(
        "RN-AU-01",
        "La sesión no es válida",
        status_code=401,
        details={"reason": motivo},
    )


def get_current_user(session: DbSessionDep) -> Usuario:
    """Usuario del access token, recargado y validado contra el tenant resuelto."""
    principal = current_principal()
    if principal is None:
        raise _sin_sesion("credenciales_invalidas")

    contexto = require_tenant()
    if principal.get("tenant_id") != str(contexto.tenant_id):
        raise _sin_sesion("token_invalido")

    try:
        usuario_id = uuid.UUID(str(principal["sub"]))
    except (KeyError, ValueError) as exc:
        raise _sin_sesion("token_invalido") from exc

    usuario = session.get(Usuario, usuario_id)
    if usuario is None or usuario.tenant_id != contexto.tenant_id or not usuario.activo:
        raise _sin_sesion("usuario_inactivo")
    return usuario


get_current_user.__requiere_auth__ = True  # type: ignore[attr-defined]
CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]


def es_dueno(usuario: Usuario) -> bool:
    """DD-08: dueño = rol profesional Y flag; un flag suelto no concede nada."""
    return usuario.rol == RolUsuario.PROFESIONAL and usuario.es_dueno


def require_role(*roles: RolUsuario) -> Callable[[Usuario], Usuario]:
    """Factoría de dependencia: 403 `RN-AU-02` si el rol no está habilitado."""
    permitidos = frozenset(roles)

    def _dependencia(usuario: CurrentUserDep) -> Usuario:
        if usuario.rol not in permitidos:
            raise DomainError(
                RN_AU_02,
                "El rol no tiene permiso para esta operación",
                status_code=403,
                details={"reason": "rol_no_habilitado"},
            )
        return usuario

    _dependencia.__rbac_roles__ = permitidos  # type: ignore[attr-defined]
    return _dependencia


def require_dueno(usuario: CurrentUserDep) -> Usuario:
    """Rutas exclusivas de dueño: exige rol profesional + `es_dueno` (RN-AU-02)."""
    if not es_dueno(usuario):
        raise DomainError(
            RN_AU_02,
            "Solo el profesional dueño puede realizar esta operación",
            status_code=403,
            details={"reason": "requiere_dueno"},
        )
    return usuario


require_dueno.__rbac_roles__ = frozenset({RolUsuario.PROFESIONAL})  # type: ignore[attr-defined]
require_dueno.__rbac_dueno__ = True  # type: ignore[attr-defined]


def alcance_agenda(usuario: Usuario) -> AlcanceAgenda:
    """Recepción y dueño ven todas las agendas; el profesional sin flag, la propia."""
    if usuario.rol == RolUsuario.RECEPCION or es_dueno(usuario):
        return AlcanceAgenda.TODAS
    return AlcanceAgenda.PROPIA


def require_acceso_profesional(
    usuario: CurrentUserDep,
    usuario_id_duenio_del_recurso: uuid.UUID,
) -> Usuario:
    """RN-AU-03: el profesional sin flag solo toca recursos de su propia identidad."""
    if alcance_agenda(usuario) is AlcanceAgenda.TODAS:
        return usuario
    if usuario.id != usuario_id_duenio_del_recurso:
        raise DomainError(
            RN_AU_03,
            "El profesional solo puede acceder a su propia agenda y pacientes",
            status_code=403,
            details={"reason": "fuera_de_alcance"},
        )
    return usuario


require_acceso_profesional.__rbac_roles__ = frozenset(RolUsuario)  # type: ignore[attr-defined]
