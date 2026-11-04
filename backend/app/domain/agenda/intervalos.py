"""Intervalos semiabiertos [desde, hasta): el fin siempre supera al inicio.

La intersección de dos intervalos usa comparaciones estrictas en ambos extremos;
por eso compartir únicamente un borde no constituye un solapamiento.
"""

from datetime import datetime, time

from app.core.errors import DomainError


def validar_intervalo[T: (time, datetime)](desde: T, hasta: T, codigo: str) -> None:
    if hasta <= desde:
        raise DomainError(
            codigo,
            "El fin debe ser posterior al inicio",
            status_code=422,
            details={"reason": "rango_invalido"},
        )
