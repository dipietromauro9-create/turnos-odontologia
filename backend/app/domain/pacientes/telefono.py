"""Normalización de teléfonos a dígitos (clave de duplicado y reutilización RN-PA-01)."""

from __future__ import annotations

import re

TELEFONO_MIN_DIGITOS = 6
TELEFONO_MAX_DIGITOS = 15

_NO_DIGITOS = re.compile(r"[^0-9]")


def solo_digitos(valor: str) -> str:
    """Quita todo lo que no sea dígito ASCII (sin validar longitud)."""
    return _NO_DIGITOS.sub("", valor)


def normalizar_telefono(valor: str) -> str:
    """Deja solo los dígitos y valida la longitud; falla con `ValueError`."""
    digitos = solo_digitos(valor)
    if not TELEFONO_MIN_DIGITOS <= len(digitos) <= TELEFONO_MAX_DIGITOS:
        msg = (
            f"El teléfono debe tener entre {TELEFONO_MIN_DIGITOS} y {TELEFONO_MAX_DIGITOS} dígitos"
        )
        raise ValueError(msg)
    return digitos


__all__ = [
    "TELEFONO_MAX_DIGITOS",
    "TELEFONO_MIN_DIGITOS",
    "normalizar_telefono",
    "solo_digitos",
]
