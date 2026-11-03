"""Endpoints de la ficha básica de pacientes (RN-PA-01/02, RN-AU-03)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.db.models import Paciente, RolUsuario
from app.db.session import TenantSession, get_session
from app.domain.auth.dependencies import CurrentUserDep, require_role
from app.domain.pacientes import service
from app.domain.pacientes.dependencies import alcance_pacientes
from app.domain.pacientes.schemas import (
    PacienteCreadoOut,
    PacienteCreate,
    PacienteOut,
    PacienteUpdate,
)

DbSessionDep = Annotated[TenantSession, Depends(get_session)]

router = APIRouter(
    prefix="/pacientes",
    tags=["pacientes"],
    dependencies=[Depends(require_role(RolUsuario.RECEPCION, RolUsuario.PROFESIONAL))],
)


def _out(paciente: Paciente) -> PacienteOut:
    return PacienteOut.model_validate(paciente)


def _creado_out(resultado: service.ResultadoCreacion) -> PacienteCreadoOut:
    return PacienteCreadoOut(
        paciente=_out(resultado.paciente),
        advertencia=resultado.advertencia,
    )


@router.get("")
def listar(
    session: DbSessionDep,
    usuario: CurrentUserDep,
    q: str | None = Query(default=None),
    limit: int = Query(default=service.LIMITE_POR_DEFECTO, ge=1, le=service.LIMITE_MAXIMO),
    offset: int = Query(default=0, ge=0),
) -> list[PacienteOut]:
    pacientes = service.buscar_pacientes(
        session,
        q=q,
        alcance=alcance_pacientes(usuario),
        usuario_id=usuario.id,
        limit=limit,
        offset=offset,
    )
    return [_out(paciente) for paciente in pacientes]


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(
    session: DbSessionDep,
    usuario: CurrentUserDep,
    datos: PacienteCreate,
) -> PacienteCreadoOut:
    resultado = service.crear_paciente(session, datos, usuario)
    session.commit()
    return _creado_out(resultado)


@router.get("/{paciente_id}")
def obtener(
    session: DbSessionDep,
    usuario: CurrentUserDep,
    paciente_id: uuid.UUID,
) -> PacienteOut:
    return _out(service.obtener_paciente(session, paciente_id, usuario))


@router.patch("/{paciente_id}")
def actualizar(
    session: DbSessionDep,
    usuario: CurrentUserDep,
    paciente_id: uuid.UUID,
    datos: PacienteUpdate,
) -> PacienteOut:
    paciente = service.actualizar_paciente(session, paciente_id, datos, usuario)
    session.commit()
    return _out(paciente)
