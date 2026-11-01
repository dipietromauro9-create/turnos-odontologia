"""Autenticación de borde: valida el access token sin tocar la base de datos.

Falla cerrado por defecto: toda ruta que no esté en la allowlist pública exige
un `Authorization: Bearer <access>` válido. El principal decodificado queda en
un `ContextVar` para que las dependencias recarguen la fila sin re-verificar.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import ErrorEnvelope
from app.core.security import TokenError, decodificar_token

RN_AU_01 = "RN-AU-01"

RUTAS_PUBLICAS = frozenset(
    {
        "/health",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
    }
)
PREFIJOS_PUBLICOS = ("/turnero/",)

_principal_ctx: ContextVar[dict[str, Any] | None] = ContextVar("auth_principal", default=None)


def current_principal() -> dict[str, Any] | None:
    """Claims del access token validado para la request en curso."""
    return _principal_ctx.get()


def es_ruta_publica(path: str) -> bool:
    if path in RUTAS_PUBLICAS:
        return True
    return path == "/turnero" or path.startswith(PREFIJOS_PUBLICOS)


def _respuesta_401(motivo: str) -> JSONResponse:
    envelope = ErrorEnvelope(
        code=RN_AU_01,
        message="La sesión no es válida",
        details={"reason": motivo},
    )
    return JSONResponse(status_code=401, content=envelope.model_dump(exclude_none=True))


class AuthMiddleware:
    """ASGI puro: firma, `exp` y `type` del access; sin acceso a la base."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or es_ruta_publica(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        cabecera = Headers(scope=scope).get("authorization", "")
        if not cabecera.startswith("Bearer "):
            await _respuesta_401("credenciales_invalidas")(scope, receive, send)
            return

        try:
            principal = decodificar_token(cabecera[7:].strip(), tipo_esperado="access")
        except TokenError as exc:
            await _respuesta_401(exc.motivo)(scope, receive, send)
            return

        token_ctx = _principal_ctx.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            _principal_ctx.reset(token_ctx)
