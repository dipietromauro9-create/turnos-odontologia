"""Rutas internas de la cola manual de recordatorios (RN-CO-03)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.db.models import RolUsuario
from app.domain.auth.dependencies import CurrentUserDep, require_role
from app.domain.recordatorios import service
from app.domain.recordatorios.schemas import RecordatorioPublic

router = APIRouter(
    prefix="/recordatorios",
    tags=["recordatorios"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


def _salida(fila: object) -> RecordatorioPublic:
    return RecordatorioPublic.model_validate(fila)


@router.get("/pendientes")
def listar_pendientes(usuario: CurrentUserDep) -> list[RecordatorioPublic]:
    return [_salida(fila) for fila in service.listar(usuario)]


@router.post("/{identificador}/enviado")
def marcar_enviado(identificador: uuid.UUID, usuario: CurrentUserDep) -> RecordatorioPublic:
    return _salida(service.marcar_enviado(identificador, usuario))


@router.post("/{identificador}/fallido")
def marcar_fallido(identificador: uuid.UUID, usuario: CurrentUserDep) -> RecordatorioPublic:
    return _salida(service.marcar_fallido(identificador, usuario))
