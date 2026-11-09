"""Rutas internas de la agenda día/semana (JWT de panel y alcance por rol)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.models import RolUsuario
from app.domain.agenda.panel import service
from app.domain.agenda.panel.schemas import AgendaOut, DiaQuery, SemanaQuery
from app.domain.auth.dependencies import CurrentUserDep, DbSessionDep, require_role

DiaQueryDep = Annotated[DiaQuery, Query()]
SemanaQueryDep = Annotated[SemanaQuery, Query()]

router = APIRouter(
    prefix="/agenda",
    tags=["agenda"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


@router.get("/dia")
def agenda_del_dia(
    usuario: CurrentUserDep,
    session: DbSessionDep,
    consulta: DiaQueryDep,
) -> AgendaOut:
    """Turnos, columnas, catálogo y bloqueos de un día calendario."""
    return service.agenda_del_dia(
        session,
        usuario,
        fecha=consulta.fecha,
        profesional_id=consulta.profesional_id,
    )


@router.get("/semana")
def agenda_de_la_semana(
    usuario: CurrentUserDep,
    session: DbSessionDep,
    consulta: SemanaQueryDep,
) -> AgendaOut:
    """Misma agregación para la semana lunes–domingo que contiene `desde`."""
    return service.agenda_de_la_semana(
        session,
        usuario,
        desde=consulta.desde,
        profesional_id=consulta.profesional_id,
    )
