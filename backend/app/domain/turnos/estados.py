"""Máquina pura RN-TU-04; la persistencia pertenece al servicio."""

from app.core.errors import DomainError
from app.db.models import EstadoTurno

TRANSICIONES = {
    EstadoTurno.RESERVADO: frozenset({EstadoTurno.CONFIRMADO, EstadoTurno.CANCELADO}),
    EstadoTurno.CONFIRMADO: frozenset(
        {EstadoTurno.ATENDIDO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE}
    ),
}


def validar_transicion(origen: EstadoTurno, destino: EstadoTurno) -> None:
    if destino not in TRANSICIONES.get(origen, frozenset()):
        raise DomainError(
            "RN-TU-04",
            "La transición solicitada no está permitida",
            422,
            details={"reason": "transicion_invalida"},
        )
