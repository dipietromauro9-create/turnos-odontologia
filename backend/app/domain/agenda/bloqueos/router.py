"""Bloqueos internos: cierres de consultorio visibles para todos los profesionales."""

import uuid

from fastapi import APIRouter, Depends, Response

from app.db.models import RolUsuario
from app.domain.agenda.bloqueos import service
from app.domain.agenda.bloqueos.schemas import BloqueoCreate, BloqueoPublic
from app.domain.agenda.dependencies import ProfesionalFiltro
from app.domain.auth.dependencies import CurrentUserDep, require_dueno, require_role

router = APIRouter(
    prefix="/bloqueos",
    tags=["agenda"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


@router.get("")
def listar_bloqueos(
    usuario: CurrentUserDep,
    profesional_id: ProfesionalFiltro = None,
) -> list[BloqueoPublic]:
    return [BloqueoPublic.model_validate(fila) for fila in service.listar(usuario, profesional_id)]


@router.post("", status_code=201, dependencies=[Depends(require_dueno)])
def crear_bloqueo(datos: BloqueoCreate) -> BloqueoPublic:
    return BloqueoPublic.model_validate(service.crear(datos))


@router.delete("/{identificador}", status_code=204, dependencies=[Depends(require_dueno)])
def eliminar_bloqueo(identificador: uuid.UUID) -> Response:
    service.eliminar(identificador)
    return Response(status_code=204)
