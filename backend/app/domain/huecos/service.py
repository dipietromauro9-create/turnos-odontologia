"""Servicio de solo lectura que combina plantilla, bloqueos y turnos activos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.errors import DomainError
from app.core.settings import get_settings
from app.domain.huecos.calculo import (
    RANGO_MAXIMO,
    BloqueoIntervalo,
    Franja,
    Hueco,
    TurnoIntervalo,
    a_zona_local,
    calcular_huecos,
)
from app.domain.huecos.repository import HuecosRepository
from app.domain.persistence import UnitOfWork


def _error(reason: str, status: int) -> DomainError:
    mensajes = {
        "no_encontrado": "El profesional o la prestación no existe",
        "referencia_inactiva": "El profesional o la prestación está desactivado",
        "rango_invalido": "El rango solicitado no es válido o supera el máximo permitido",
    }
    return DomainError(
        "RN-AG-01",
        mensajes[reason],
        status_code=status,
        details={"reason": reason},
    )


def _dias_del_rango(desde: datetime, hasta: datetime) -> set[int]:
    ultimo = (hasta - timedelta(microseconds=1)).date()
    dias: set[int] = set()
    dia = desde.date()
    while dia <= ultimo:
        dias.add(dia.weekday())
        dia += timedelta(days=1)
    return dias


def enumerar_huecos(
    profesional_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    desde: datetime,
    hasta: datetime,
    *,
    ahora: datetime | None = None,
) -> list[Hueco]:
    """Enumera huecos reservables con un reloj inyectable; nunca escribe (R4)."""
    if hasta <= desde or hasta - desde > RANGO_MAXIMO:
        raise _error("rango_invalido", 422)

    tz = ZoneInfo(get_settings().tz)
    desde_local = a_zona_local(desde, tz)
    hasta_local = a_zona_local(hasta, tz)
    ahora_local = a_zona_local(ahora or datetime.now(UTC), tz)

    with UnitOfWork() as uow:
        repo = HuecosRepository(uow.session)
        profesional = repo.obtener_profesional(profesional_id)
        if profesional is None:
            raise _error("no_encontrado", 404)
        if not profesional.activo:
            raise _error("referencia_inactiva", 422)

        prestacion = repo.obtener_prestacion(prestacion_id)
        if prestacion is None:
            raise _error("no_encontrado", 404)
        if not prestacion.activa:
            raise _error("referencia_inactiva", 422)

        dias = _dias_del_rango(desde_local, hasta_local)
        franjas = [
            Franja(
                dia_semana=franja.dia_semana,
                hora_desde=franja.hora_desde,
                hora_hasta=franja.hora_hasta,
            )
            for franja in repo.franjas(profesional_id, dias)
        ]
        bloqueos = [
            BloqueoIntervalo(
                profesional_id=bloqueo.profesional_id,
                desde=bloqueo.desde,
                hasta=bloqueo.hasta,
            )
            for bloqueo in repo.bloqueos(profesional_id, desde_local, hasta_local)
        ]
        turnos = [
            TurnoIntervalo(
                profesional_id=turno.profesional_id,
                inicio=turno.inicio,
                fin=turno.fin,
                estado=turno.estado,
            )
            for turno in repo.turnos(profesional_id, desde_local, hasta_local)
        ]

        return calcular_huecos(
            profesional_id=profesional.id,
            prestacion_id=prestacion.id,
            duracion_min=prestacion.duracion_min,
            desde=desde_local,
            hasta=hasta_local,
            disponibilidad=franjas,
            bloqueos=bloqueos,
            turnos=turnos,
            ahora=ahora_local,
            tz=tz,
        )
