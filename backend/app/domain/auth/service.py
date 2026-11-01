"""Servicio de autenticación: login, rotación de refresh y logout.

La autoridad es la fila `Usuario` del tenant resuelto (R3); el estado efímero
(bloqueo, cuota, blacklist) vive en el `TokenStore` inyectado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.security import (
    TokenError,
    crear_token,
    decodificar_token,
    verificar_password_ficticia,
    verify_password,
)
from app.core.settings import get_settings
from app.core.token_store import TokenStore
from app.db.models import Usuario
from app.db.session import require_tenant

RN_AU_01 = "RN-AU-01"


@dataclass(frozen=True)
class SesionEmitida:
    """Par de tokens recién emitido, listo para el router."""

    access_token: str
    refresh_token: str
    expires_in: int


def _credenciales_invalidas() -> DomainError:
    return DomainError(
        RN_AU_01,
        "Credenciales inválidas",
        status_code=401,
        details={"reason": "credenciales_invalidas"},
    )


def _sesion_invalida(motivo: str) -> DomainError:
    return DomainError(
        RN_AU_01,
        "La sesión no es válida",
        status_code=401,
        details={"reason": motivo},
    )


def _demasiados_intentos(motivo: str, reintentar_en: int) -> DomainError:
    espera = max(int(reintentar_en), 1)
    return DomainError(
        RN_AU_01,
        "Demasiados intentos de inicio de sesión",
        status_code=429,
        details={"reason": motivo, "retry_after": espera},
        headers={"Retry-After": str(espera)},
    )


def _buscar_usuario(session: Session, email: str) -> Usuario | None:
    contexto = require_tenant()
    return session.execute(
        select(Usuario).where(
            Usuario.email == email,
            Usuario.tenant_id == contexto.tenant_id,
        )
    ).scalar_one_or_none()


def _cargar_usuario(session: Session, sub: str) -> Usuario | None:
    try:
        usuario_id = uuid.UUID(str(sub))
    except ValueError:
        return None
    return session.get(Usuario, usuario_id)


def _emitir_par(usuario: Usuario) -> SesionEmitida:
    roles = [usuario.rol.value]
    access = crear_token(
        sub=usuario.id,
        tenant_id=usuario.tenant_id,
        email=usuario.email,
        roles=roles,
        tipo="access",
    )
    refresh = crear_token(
        sub=usuario.id,
        tenant_id=usuario.tenant_id,
        email=usuario.email,
        roles=roles,
        tipo="refresh",
    )
    return SesionEmitida(
        access_token=access,
        refresh_token=refresh,
        expires_in=get_settings().access_minutes * 60,
    )


def _contabilizar_fallo(store: TokenStore, usuario: Usuario) -> None:
    store.registrar_fallo(usuario.tenant_id, usuario.id)


def _contabilizar_exito(store: TokenStore, usuario: Usuario) -> None:
    store.limpiar_fallos(usuario.tenant_id, usuario.id)


def _verificar_credenciales(*, usuario: Usuario | None, password: str) -> Usuario:
    """Solo decide si las credenciales sirven; no toca la contabilidad del store."""
    if usuario is None:
        verificar_password_ficticia(password)
        raise _credenciales_invalidas()
    if not verify_password(password, usuario.password_hash) or not usuario.activo:
        raise _credenciales_invalidas()
    return usuario


def autenticar(
    *,
    session: Session,
    store: TokenStore,
    email: str,
    password: str,
    ip: str,
) -> SesionEmitida:
    """Login: bloqueo por cuenta, cuota por IP+email y verificación Argon2id."""
    usuario = _buscar_usuario(session, email)
    if usuario is not None:
        bloqueo = store.esta_bloqueado(usuario.tenant_id, usuario.id)
        if bloqueo:
            raise _demasiados_intentos("cuenta_bloqueada", bloqueo.reintentar_en)

    cuota = store.consumir_cuota(ip, email)
    if not cuota:
        raise _demasiados_intentos("rate_limit", cuota.reintentar_en)

    try:
        autenticado = _verificar_credenciales(usuario=usuario, password=password)
    except DomainError:
        if usuario is not None:
            _contabilizar_fallo(store, usuario)
        raise

    _contabilizar_exito(store, autenticado)
    return _emitir_par(autenticado)


def _segundos_hasta(exp: int) -> int:
    restante = int(exp) - int(datetime.now(UTC).timestamp())
    return max(restante, 1)


def rotar_sesion(
    *, session: Session, store: TokenStore, refresh_token: str | None
) -> SesionEmitida:
    """Rotación: valida tipo/tenant/blacklist y revoca el `jti` viejo con `SET NX`."""
    if not refresh_token:
        raise _sesion_invalida("token_invalido")
    try:
        payload = decodificar_token(refresh_token, tipo_esperado="refresh")
    except TokenError as exc:
        raise _sesion_invalida(exc.motivo) from exc

    contexto = require_tenant()
    if payload.get("tenant_id") != str(contexto.tenant_id):
        raise _sesion_invalida("token_invalido")

    jti = str(payload["jti"])
    if store.esta_revocado(jti):
        raise _sesion_invalida("refresh_revocado")

    usuario = _cargar_usuario(session, str(payload["sub"]))
    if usuario is None or not usuario.activo:
        raise _sesion_invalida("usuario_inactivo")

    if not store.revocar(jti, _segundos_hasta(int(payload["exp"]))):
        raise _sesion_invalida("refresh_revocado")

    return _emitir_par(usuario)


def cerrar_sesion(*, store: TokenStore, refresh_token: str | None) -> None:
    """Logout idempotente: revoca el refresh si se puede; nunca falla por ausencia."""
    if not refresh_token:
        return
    try:
        payload = decodificar_token(refresh_token, tipo_esperado="refresh")
    except TokenError:
        return
    store.revocar(str(payload["jti"]), _segundos_hasta(int(payload["exp"])))
