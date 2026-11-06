"""Endpoint interno de huecos: JWT de panel, alcance por rol y respuesta sin PII."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.models import RolUsuario
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.auth.dependencies import CurrentUserDep, DbSessionDep, require_role
from app.domain.huecos.schemas import HuecoPublic, HuecosQuery
from app.domain.huecos.service import enumerar_huecos

HuecosQueryDep = Annotated[HuecosQuery, Query()]

router = APIRouter(
    prefix="/disponibilidad",
    tags=["agenda"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


@router.get("/huecos")
def listar_huecos(
    usuario: CurrentUserDep,
    session: DbSessionDep,
    consulta: HuecosQueryDep,
) -> list[HuecoPublic]:
    """Enumera huecos del profesional solicitado respetando el alcance RBAC."""
    resuelto = profesional_del_alcance(session, usuario, consulta.profesional_id)
    profesional_id = resuelto if resuelto is not None else consulta.profesional_id
    return [
        HuecoPublic.model_validate(hueco)
        for hueco in enumerar_huecos(
            profesional_id,
            consulta.prestacion_id,
            consulta.desde,
            consulta.hasta,
        )
    ]
