"""Endpoints dueño-only del directorio de profesionales (RN-AU-02)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.db.models import Profesional
from app.domain.agenda.profesionales import service
from app.domain.agenda.profesionales.schemas import (
    ProfesionalCreate,
    ProfesionalOut,
    ProfesionalUpdate,
)
from app.domain.auth.dependencies import require_dueno

router = APIRouter(
    prefix="/profesionales",
    tags=["profesionales"],
    dependencies=[Depends(require_dueno)],
)


def _out(profesional: Profesional) -> ProfesionalOut:
    return ProfesionalOut.model_validate(profesional)


@router.get("")
def listar(activo: bool | None = Query(default=None)) -> list[ProfesionalOut]:
    return [_out(profesional) for profesional in service.listar(activo=activo)]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(datos: ProfesionalCreate) -> ProfesionalOut:
    return _out(service.crear(datos))


@router.get("/{profesional_id}")
def obtener(profesional_id: uuid.UUID) -> ProfesionalOut:
    return _out(service.obtener(profesional_id))


@router.patch("/{profesional_id}")
def actualizar(profesional_id: uuid.UUID, datos: ProfesionalUpdate) -> ProfesionalOut:
    return _out(service.actualizar(profesional_id, datos))
