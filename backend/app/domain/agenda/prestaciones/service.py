"""Servicio del catálogo de prestaciones: validación, persistencia y errores de dominio."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.db.models import Prestacion
from app.domain.agenda.prestaciones.schemas import PrestacionCreate, PrestacionUpdate
from app.domain.persistence import UnitOfWork

RN_AG_03 = "RN-AG-03"
RN_GL_01 = "RN-GL-01"
MULTIPLO_DURACION = 5


def validar_duracion(duracion_min: int) -> None:
    """RN-AG-03: duración positiva y múltiplo de 5 (422 con sobre de dominio)."""
    if duracion_min <= 0 or duracion_min % MULTIPLO_DURACION != 0:
        raise DomainError(
            RN_AG_03,
            "La duración debe ser mayor que cero y múltiplo de 5 minutos",
            status_code=422,
            details={"reason": "duracion_invalida", "duracion_min": duracion_min},
        )


def _no_encontrada() -> DomainError:
    return DomainError(
        RN_GL_01,
        "La prestación no existe",
        status_code=404,
        details={"reason": "no_encontrado"},
    )


def _duracion_rechazada_por_la_base() -> DomainError:
    return DomainError(
        RN_AG_03,
        "La duración debe ser mayor que cero y múltiplo de 5 minutos",
        status_code=422,
        details={"reason": "duracion_invalida"},
    )


def _validar_cambios(cambios: dict[str, Any]) -> None:
    if "duracion_min" in cambios:
        duracion = cambios["duracion_min"]
        if duracion is None:
            raise _duracion_rechazada_por_la_base()
        validar_duracion(duracion)
    if "nombre" in cambios and cambios["nombre"] is None:
        raise DomainError(
            RN_GL_01,
            "El nombre no puede estar vacío",
            status_code=422,
            details={"reason": "nombre_invalido"},
        )


def _refrescar(uow: UnitOfWork, prestacion: Prestacion) -> None:
    """Trae los defaults del servidor antes de cerrar la sesión (Objeto desacoplado)."""
    uow.session.refresh(prestacion)


def listar(*, activa: bool | None = None) -> list[Prestacion]:
    with UnitOfWork() as uow:
        filtros: dict[str, Any] = {} if activa is None else {"activa": activa}
        prestaciones = uow.repository(Prestacion).list(**filtros)
        return sorted(prestaciones, key=lambda prestacion: prestacion.nombre)


def obtener(prestacion_id: uuid.UUID) -> Prestacion:
    with UnitOfWork() as uow:
        prestacion = uow.repository(Prestacion).get(prestacion_id)
        if prestacion is None:
            raise _no_encontrada()
        return prestacion


def crear(datos: PrestacionCreate) -> Prestacion:
    validar_duracion(datos.duracion_min)
    with UnitOfWork() as uow:
        repositorio = uow.repository(Prestacion)
        try:
            prestacion = repositorio.add(
                Prestacion(
                    nombre=datos.nombre,
                    duracion_min=datos.duracion_min,
                    precio_ref=datos.precio_ref,
                    activa=datos.activa,
                )
            )
        except IntegrityError as exc:
            uow.session.rollback()
            raise _duracion_rechazada_por_la_base() from exc
        _refrescar(uow, prestacion)
        return prestacion


def actualizar(prestacion_id: uuid.UUID, datos: PrestacionUpdate) -> Prestacion:
    cambios = datos.model_dump(exclude_unset=True)
    _validar_cambios(cambios)
    with UnitOfWork() as uow:
        repositorio = uow.repository(Prestacion)
        try:
            prestacion = repositorio.update(prestacion_id, **cambios)
        except IntegrityError as exc:
            uow.session.rollback()
            raise _duracion_rechazada_por_la_base() from exc
        if prestacion is None:
            raise _no_encontrada()
        _refrescar(uow, prestacion)
        return prestacion


def desactivar(prestacion_id: uuid.UUID) -> Prestacion:
    with UnitOfWork() as uow:
        repositorio = uow.repository(Prestacion)
        prestacion = repositorio.get(prestacion_id)
        if prestacion is None:
            raise _no_encontrada()
        if prestacion.activa:
            prestacion.activa = False
            uow.session.flush()
        _refrescar(uow, prestacion)
        return prestacion


__all__ = [
    "actualizar",
    "crear",
    "desactivar",
    "listar",
    "obtener",
    "validar_duracion",
]
