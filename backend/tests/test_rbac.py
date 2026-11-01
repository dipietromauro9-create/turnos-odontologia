"""RBAC: matriz de roles, dueño como flag y alcance del profesional (RN-AU-02/03).

El router se monta en el propio test (mismo patrón que `_app_de_dominio()` de
`test_tenancy_session.py`) porque C-03 entrega helpers, no endpoints de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import register_handlers
from app.core.security import crear_token
from app.db.models import RolUsuario, Usuario
from app.db.session import TenantContextMiddleware
from app.domain.auth.dependencies import (
    AlcanceAgenda,
    alcance_agenda,
    es_dueno,
    get_current_user,
    require_acceso_profesional,
    require_dueno,
    require_role,
)
from app.domain.auth.middleware import AuthMiddleware
from tests.auth_helpers import PASSWORD
from tests.factories import crear_tenant, crear_usuario_con_password

pytestmark = pytest.mark.integration


def _app_de_rbac() -> FastAPI:
    app = FastAPI()
    register_handlers(app)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(TenantContextMiddleware)

    panel = APIRouter(prefix="/panel", tags=["panel"])

    @panel.get("/profesional")
    def solo_profesional(
        _usuario: Annotated[Usuario, Depends(require_role(RolUsuario.PROFESIONAL))],
    ) -> dict[str, str]:
        return {"ok": "profesional"}

    @panel.get("/config")
    def config(_usuario: Annotated[Usuario, Depends(require_dueno)]) -> dict[str, str]:
        return {"ok": "config"}

    @panel.get("/usuarios")
    def usuarios(_usuario: Annotated[Usuario, Depends(require_dueno)]) -> dict[str, str]:
        return {"ok": "usuarios"}

    @panel.get("/export")
    def export(_usuario: Annotated[Usuario, Depends(require_dueno)]) -> dict[str, str]:
        return {"ok": "export"}

    @panel.get("/agenda/{usuario_id_duenio_del_recurso}")
    def agenda(
        _usuario: Annotated[Usuario, Depends(require_acceso_profesional)],
    ) -> dict[str, str]:
        return {"ok": "agenda"}

    app.include_router(panel)
    return app


@dataclass(frozen=True)
class Panel:
    app: FastAPI
    dueno: Usuario
    profesional: Usuario
    recepcion: Usuario


@pytest.fixture()
def panel(app_env: None, session_factory: sessionmaker[Session]) -> Panel:
    with session_factory() as session:
        tenant = crear_tenant(session)
        dueno = crear_usuario_con_password(
            session,
            tenant,
            "dueno@demo",
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
            es_dueno=True,
        )
        profesional = crear_usuario_con_password(
            session,
            tenant,
            "profesional@demo",
            PASSWORD,
            rol=RolUsuario.PROFESIONAL,
        )
        recepcion = crear_usuario_con_password(
            session, tenant, "recepcion@demo", PASSWORD, rol=RolUsuario.RECEPCION
        )
    return Panel(app=_app_de_rbac(), dueno=dueno, profesional=profesional, recepcion=recepcion)


def _token(usuario: Usuario) -> str:
    return crear_token(
        sub=usuario.id,
        tenant_id=usuario.tenant_id,
        email=usuario.email,
        roles=[usuario.rol.value],
        tipo="access",
    )


def _get(panel: Panel, path: str, usuario: Usuario | None = None) -> object:
    headers = {"Authorization": f"Bearer {_token(usuario)}"} if usuario is not None else {}
    return TestClient(panel.app).get(path, headers=headers)


def test_sin_token_responde_401_antes_de_evaluar_roles(panel: Panel) -> None:
    respuesta = _get(panel, "/panel/config")

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


def test_un_rol_no_habilitado_recibe_403(panel: Panel) -> None:
    respuesta = _get(panel, "/panel/profesional", panel.recepcion)

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_un_rol_habilitado_accede(panel: Panel) -> None:
    respuesta = _get(panel, "/panel/profesional", panel.profesional)

    assert respuesta.status_code == 200


@pytest.mark.parametrize("ruta", ["/panel/config", "/panel/usuarios", "/panel/export"])
def test_recepcion_recibe_403_en_configuracion_usuarios_y_export(panel: Panel, ruta: str) -> None:
    respuesta = _get(panel, ruta, panel.recepcion)

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_el_dueno_accede_a_las_rutas_de_dueno(panel: Panel) -> None:
    respuesta = _get(panel, "/panel/config", panel.dueno)

    assert respuesta.status_code == 200


def test_el_profesional_sin_flag_recibe_403(panel: Panel) -> None:
    respuesta = _get(panel, "/panel/config", panel.profesional)

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_un_flag_de_dueno_sobre_recepcion_no_concede_permisos(
    panel: Panel,
) -> None:
    falso_dueno = Usuario(
        tenant_id=panel.recepcion.tenant_id,
        nombre="Recepción Ficticia",
        email="falso-dueno@demo",
        password_hash="no-se-usa",
        rol=RolUsuario.RECEPCION,
        es_dueno=True,
        activo=True,
    )
    panel.app.dependency_overrides[get_current_user] = lambda: falso_dueno
    try:
        respuesta = _get(panel, "/panel/config", panel.dueno)
    finally:
        panel.app.dependency_overrides.clear()

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-02"


def test_un_profesional_no_ve_la_agenda_de_otro(panel: Panel) -> None:
    respuesta = _get(panel, f"/panel/agenda/{panel.dueno.id}", panel.profesional)

    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "RN-AU-03"


def test_un_profesional_ve_su_propia_agenda(panel: Panel) -> None:
    respuesta = _get(panel, f"/panel/agenda/{panel.profesional.id}", panel.profesional)

    assert respuesta.status_code == 200


def test_el_dueno_ve_la_agenda_de_cualquier_profesional(panel: Panel) -> None:
    respuesta = _get(panel, f"/panel/agenda/{panel.profesional.id}", panel.dueno)

    assert respuesta.status_code == 200


def test_la_recepcion_ve_la_agenda_de_cualquier_profesional(panel: Panel) -> None:
    respuesta = _get(panel, f"/panel/agenda/{panel.profesional.id}", panel.recepcion)

    assert respuesta.status_code == 200


def test_alcance_agenda_distingue_propia_de_todas(panel: Panel) -> None:
    assert alcance_agenda(panel.profesional) is AlcanceAgenda.PROPIA
    assert alcance_agenda(panel.dueno) is AlcanceAgenda.TODAS
    assert alcance_agenda(panel.recepcion) is AlcanceAgenda.TODAS


def test_es_dueno_exige_rol_profesional_y_flag(panel: Panel) -> None:
    assert es_dueno(panel.dueno) is True
    assert es_dueno(panel.profesional) is False
    assert (
        es_dueno(
            Usuario(
                tenant_id=panel.recepcion.tenant_id,
                nombre="Recepción Ficticia",
                email="flag-sin-rol@demo",
                password_hash="no-se-usa",
                rol=RolUsuario.RECEPCION,
                es_dueno=True,
                activo=True,
            )
        )
        is False
    )
