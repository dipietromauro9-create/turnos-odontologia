"""Endpoints dueño-only del catálogo de prestaciones (RN-AU-02)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.db.models import Prestacion
from app.domain.agenda.prestaciones import service
from app.domain.agenda.prestaciones.schemas import (
    PrestacionCreate,
    PrestacionOut,
    PrestacionUpdate,
)
from app.domain.auth.dependencies import require_dueno

router = APIRouter(
    prefix="/prestaciones",
    tags=["prestaciones"],
    dependencies=[Depends(require_dueno)],
)


def _out(prestacion: Prestacion) -> PrestacionOut:
    return PrestacionOut.model_validate(prestacion)


@router.get("")
def listar(activa: bool | None = Query(default=None)) -> list[PrestacionOut]:
    return [_out(prestacion) for prestacion in service.listar(activa=activa)]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(datos: PrestacionCreate) -> PrestacionOut:
    return _out(service.crear(datos))


@router.get("/{prestacion_id}")
def obtener(prestacion_id: uuid.UUID) -> PrestacionOut:
    return _out(service.obtener(prestacion_id))


@router.patch("/{prestacion_id}")
def actualizar(prestacion_id: uuid.UUID, datos: PrestacionUpdate) -> PrestacionOut:
    return _out(service.actualizar(prestacion_id, datos))


@router.post("/{prestacion_id}/desactivar")
def desactivar(prestacion_id: uuid.UUID) -> PrestacionOut:
    return _out(service.desactivar(prestacion_id))
