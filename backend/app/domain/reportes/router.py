"""Rutas de reportes: solo profesional, con alcance por rol (RN-AU-02)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.models import RolUsuario
from app.domain.auth.dependencies import CurrentUserDep, require_role
from app.domain.reportes import service
from app.domain.reportes.schemas import (
    AusenciasProfesional,
    OcupacionProfesional,
    RecordatoriosProfesional,
    ReporteFiltros,
)

router = APIRouter(
    prefix="/reportes",
    tags=["reportes"],
    dependencies=[Depends(require_role(RolUsuario.PROFESIONAL))],
)
FiltrosDep = Annotated[ReporteFiltros, Query()]


@router.get("/ocupacion")
def reporte_ocupacion(
    usuario: CurrentUserDep, filtros: FiltrosDep
) -> list[OcupacionProfesional]:
    return service.ocupacion(usuario, filtros)


@router.get("/ausencias")
def reporte_ausencias(
    usuario: CurrentUserDep, filtros: FiltrosDep
) -> list[AusenciasProfesional]:
    return service.ausencias(usuario, filtros)


@router.get("/recordatorios")
def reporte_recordatorios(
    usuario: CurrentUserDep, filtros: FiltrosDep
) -> list[RecordatoriosProfesional]:
    return service.recordatorios(usuario, filtros)
