"""Primitivas de seguridad: contraseñas Argon2id y tokens JWT HS256."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.settings import get_settings

TipoToken = Literal["access", "refresh"]

CLAIMS_REQUERIDOS = (
    "sub",
    "tenant_id",
    "roles",
    "email",
    "jti",
    "type",
    "iat",
    "exp",
)

_hasher = PasswordHasher()

_HASH_FICTICIO = _hasher.hash("hash-ficticio-de-tiempo-constante")


class TokenError(Exception):
    """Token JWT inválido o expirado; `motivo` distingue ambos casos."""

    def __init__(self, motivo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.motivo = motivo


def hash_password(password: str) -> str:
    """Devuelve un hash Argon2id con salt aleatorio."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica sin filtrar excepciones ni distinguir hash inválido de no coincidencia."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verificar_password_ficticia(password: str) -> None:
    """Quema el mismo tiempo que una verificación real cuando el email no existe."""
    with contextlib.suppress(VerificationError, InvalidHashError):
        _hasher.verify(_HASH_FICTICIO, password)


def crear_token(
    *,
    sub: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    email: str,
    roles: Sequence[str],
    tipo: TipoToken,
    ahora: datetime | None = None,
) -> str:
    """Emite un JWT HS256 con los claims exactos del contrato y vida por configuración."""
    settings = get_settings()
    emitido = ahora or datetime.now(UTC)
    if tipo == "access":
        vida = timedelta(minutes=settings.access_minutes)
    elif tipo == "refresh":
        vida = timedelta(days=settings.refresh_days)
    else:
        msg = f"Tipo de token no soportado: {tipo}"
        raise ValueError(msg)

    payload = {
        "sub": str(sub),
        "tenant_id": str(tenant_id),
        "roles": list(roles),
        "email": email,
        "jti": str(uuid.uuid4()),
        "type": tipo,
        "iat": int(emitido.timestamp()),
        "exp": int((emitido + vida).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decodificar_token(token: str, *, tipo_esperado: TipoToken) -> dict[str, Any]:
    """Valida firma, expiración, claims requeridos y tipo; lanza `TokenError` si falla."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": list(CLAIMS_REQUERIDOS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expirado", "El token expiró") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token_invalido", "El token no es válido") from exc

    if payload.get("type") != tipo_esperado:
        raise TokenError("token_invalido", "El tipo de token no es el esperado")
    return payload
