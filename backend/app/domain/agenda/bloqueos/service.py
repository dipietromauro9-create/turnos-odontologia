"""Cierres de agenda transaccionales, con alcance por rol (RN-AG-02)."""

import uuid

from app.core.errors import DomainError
from app.db.models import Bloqueo, Profesional, Usuario
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.agenda.bloqueos.repository import BloqueoRepository
from app.domain.agenda.bloqueos.schemas import BloqueoCreate
from app.domain.agenda.intervalos import validar_intervalo
from app.domain.persistence import UnitOfWork


def _no_encontrado() -> DomainError:
    return DomainError(
        "RN-AG-02",
        "El bloqueo o el profesional no existe",
        status_code=404,
        details={"reason": "no_encontrado"},
    )


def crear(datos: BloqueoCreate) -> Bloqueo:
    validar_intervalo(datos.desde, datos.hasta, "RN-AG-02")
    with UnitOfWork() as uow:
        if datos.profesional_id is not None and (
            uow.repository(Profesional).get(datos.profesional_id) is None
        ):
            raise _no_encontrado()
        fila = BloqueoRepository(uow.session).add(Bloqueo(**datos.model_dump()))
        uow.session.refresh(fila)
        return fila


def listar(usuario: Usuario, profesional_id: uuid.UUID | None = None) -> list[Bloqueo]:
    with UnitOfWork() as uow:
        profesional_id = profesional_del_alcance(uow.session, usuario, profesional_id)
        return BloqueoRepository(uow.session).listar(profesional_id)


def eliminar(identificador: uuid.UUID) -> None:
    with UnitOfWork() as uow:
        if not BloqueoRepository(uow.session).delete(identificador):
            raise _no_encontrado()
