"""Plantilla semanal interna: lectura por alcance y escritura exclusiva del dueño."""

import uuid

from fastapi import APIRouter, Depends, Response

from app.db.models import RolUsuario
from app.domain.agenda.dependencies import ProfesionalFiltro
from app.domain.agenda.disponibilidad import service
from app.domain.agenda.disponibilidad.schemas import DisponibilidadCreate, DisponibilidadPublic
from app.domain.auth.dependencies import CurrentUserDep, require_dueno, require_role

router = APIRouter(
    prefix="/disponibilidad",
    tags=["agenda"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


@router.get("")
def listar_disponibilidad(
    usuario: CurrentUserDep,
    profesional_id: ProfesionalFiltro = None,
) -> list[DisponibilidadPublic]:
    return [
        DisponibilidadPublic.model_validate(fila)
        for fila in service.listar(usuario, profesional_id)
    ]


@router.post("", status_code=201, dependencies=[Depends(require_dueno)])
def crear_disponibilidad(datos: DisponibilidadCreate) -> DisponibilidadPublic:
    return DisponibilidadPublic.model_validate(service.crear(datos))


@router.delete("/{identificador}", status_code=204, dependencies=[Depends(require_dueno)])
def eliminar_disponibilidad(identificador: uuid.UUID) -> Response:
    service.eliminar(identificador)
    return Response(status_code=204)
