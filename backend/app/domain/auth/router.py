"""Endpoints de sesión del panel. Las rutas se montan con prefijo propio."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.core.settings import get_settings
from app.domain.auth.dependencies import CurrentUserDep, DbSessionDep, TokenStoreDep
from app.domain.auth.schemas import LoginIn, MeOut, TokenOut
from app.domain.auth.service import SesionEmitida, autenticar, cerrar_sesion, rotar_sesion

COOKIE_REFRESH = "refresh_token"

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


def _token_out(sesion: SesionEmitida) -> TokenOut:
    return TokenOut(
        access_token=sesion.access_token,
        token_type="bearer",
        expires_in=sesion.expires_in,
    )


def _cookie_secure() -> bool:
    """En producción el frontend es https; en local http evita descartar la cookie."""
    return get_settings().frontend_origin.startswith("https://")


def _guardar_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_REFRESH,
        value=token,
        max_age=settings.refresh_days * 24 * 60 * 60,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )


def _borrar_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_REFRESH,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )


@router.post("/login")
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: DbSessionDep,
    store: TokenStoreDep,
) -> TokenOut:
    sesion = autenticar(
        session=session,
        store=store,
        email=payload.email,
        password=payload.password,
        ip=_ip(request),
    )
    _guardar_cookie(response, sesion.refresh_token)
    return _token_out(sesion)


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    session: DbSessionDep,
    store: TokenStoreDep,
) -> TokenOut:
    sesion = rotar_sesion(
        session=session,
        store=store,
        refresh_token=request.cookies.get(COOKIE_REFRESH),
    )
    _guardar_cookie(response, sesion.refresh_token)
    return _token_out(sesion)


@router.get("/me")
def me(usuario: CurrentUserDep) -> MeOut:
    return MeOut(
        id=usuario.id,
        tenant_id=usuario.tenant_id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        es_dueno=usuario.es_dueno,
    )


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, store: TokenStoreDep) -> None:
    cerrar_sesion(store=store, refresh_token=request.cookies.get(COOKIE_REFRESH))
    _borrar_cookie(response)
