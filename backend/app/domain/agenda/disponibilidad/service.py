"""Único camino de escritura de la plantilla semanal (RN-AG-01)."""

import uuid

from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.db.models import Disponibilidad, Profesional, Usuario
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.agenda.disponibilidad.repository import DisponibilidadRepository
from app.domain.agenda.disponibilidad.schemas import DisponibilidadCreate
from app.domain.agenda.intervalos import validar_intervalo
from app.domain.persistence import UnitOfWork


def _error(reason: str, status: int = 404) -> DomainError:
    mensajes = {
        "rango_invalido": "La hora de fin debe ser posterior al inicio",
        "rango_solapado": "La franja se superpone con otra existente",
        "no_encontrado": "La franja o el profesional no existe",
    }
    return DomainError("RN-AG-01", mensajes[reason], status_code=status, details={"reason": reason})


def crear(datos: DisponibilidadCreate) -> Disponibilidad:
    validar_intervalo(datos.hora_desde, datos.hora_hasta, "RN-AG-01")
    with UnitOfWork() as uow:
        if uow.repository(Profesional).get(datos.profesional_id) is None:
            raise _error("no_encontrado")
        repositorio = DisponibilidadRepository(uow.session)
        if repositorio.intersecta(
            datos.profesional_id, datos.dia_semana, datos.hora_desde, datos.hora_hasta
        ):
            raise _error("rango_solapado", 409)
        try:
            fila = repositorio.add(Disponibilidad(**datos.model_dump()))
        except IntegrityError as exc:
            if getattr(exc.orig.diag, "constraint_name", None) != (
                "uq_disponibilidad_tenant_profesional_dia_rango"
            ):
                raise
            raise _error("rango_solapado", 409) from exc
        uow.session.refresh(fila)
        return fila


def listar(usuario: Usuario, profesional_id: uuid.UUID | None = None) -> list[Disponibilidad]:
    with UnitOfWork() as uow:
        profesional_id = profesional_del_alcance(uow.session, usuario, profesional_id)
        return DisponibilidadRepository(uow.session).listar(profesional_id)


def eliminar(identificador: uuid.UUID) -> None:
    with UnitOfWork() as uow:
        if not DisponibilidadRepository(uow.session).delete(identificador):
            raise _error("no_encontrado")
