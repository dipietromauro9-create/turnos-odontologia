"""Rutas internas autenticadas; toda escritura delega al servicio de turnos."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.models import EstadoTurno, RolUsuario, Turno
from app.domain.auth.dependencies import CurrentUserDep, require_role
from app.domain.turnos import service
from app.domain.turnos.schemas import (
    AccionVacia,
    CancelarTurno,
    TurnoCreate,
    TurnoEstado,
    TurnoFiltros,
    TurnoPublic,
    TurnoReprogramar,
)

router = APIRouter(
    prefix="/turnos",
    tags=["turnos"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)
FiltrosDep = Annotated[TurnoFiltros, Query()]


def _salida(fila: Turno) -> TurnoPublic:
    return TurnoPublic.model_validate(fila)


@router.get("")
def listar_turnos(usuario: CurrentUserDep, filtros: FiltrosDep) -> list[TurnoPublic]:
    return [_salida(fila) for fila in service.listar(usuario, filtros)]


@router.post("", status_code=201)
def crear_turno(datos: TurnoCreate, usuario: CurrentUserDep) -> TurnoPublic:
    return _salida(service.crear(datos, usuario))


@router.get("/{identificador}")
def obtener_turno(identificador: uuid.UUID, usuario: CurrentUserDep) -> TurnoPublic:
    return _salida(service.obtener(identificador, usuario))


@router.patch("/{identificador}")
def cambiar_estado(
    identificador: uuid.UUID, datos: TurnoEstado, usuario: CurrentUserDep
) -> TurnoPublic:
    return _salida(
        service.transicionar(
            identificador, datos.estado, usuario, motivo_cancelacion=datos.motivo_cancelacion
        )
    )


@router.post("/{identificador}/confirmar")
def confirmar(
    identificador: uuid.UUID, usuario: CurrentUserDep, datos: AccionVacia | None = None
) -> TurnoPublic:
    return _salida(service.transicionar(identificador, EstadoTurno.CONFIRMADO, usuario))


@router.post("/{identificador}/atender")
def atender(
    identificador: uuid.UUID, usuario: CurrentUserDep, datos: AccionVacia | None = None
) -> TurnoPublic:
    return _salida(service.transicionar(identificador, EstadoTurno.ATENDIDO, usuario))


@router.post("/{identificador}/cancelar")
def cancelar(
    identificador: uuid.UUID, usuario: CurrentUserDep, datos: CancelarTurno | None = None
) -> TurnoPublic:
    motivo = datos.motivo_cancelacion if datos is not None else None
    return _salida(
        service.transicionar(
            identificador, EstadoTurno.CANCELADO, usuario, motivo_cancelacion=motivo
        )
    )


@router.post("/{identificador}/registrar-ausencia")
def registrar_ausencia(
    identificador: uuid.UUID, usuario: CurrentUserDep, datos: AccionVacia | None = None
) -> TurnoPublic:
    return _salida(service.transicionar(identificador, EstadoTurno.AUSENTE, usuario))


@router.post("/{identificador}/reprogramar")
def reprogramar(
    identificador: uuid.UUID, datos: TurnoReprogramar, usuario: CurrentUserDep
) -> TurnoPublic:
    return _salida(service.reprogramar(identificador, datos.nuevo_inicio, usuario))
