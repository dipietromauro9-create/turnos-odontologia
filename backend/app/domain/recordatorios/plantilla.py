"""Plantilla y ventana de los recordatorios manuales (RN-CO-02, RN-GL-03).

Funciones puras: sin I/O, sin reloj global y sin configuración implícita, para
poder testear la generación del texto sin base de datos.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.huecos.calculo import a_zona_local

_FORMATO_FECHA = "%d/%m/%Y"
_FORMATO_HORA = "%H:%M"


def parse_ventana(valor: str) -> tuple[int, int]:
    """Parsea `RECORDATORIO_VENTANA_HS` (`"24,48"`) a `(min_hs, max_hs)`."""
    try:
        minimo, maximo = (int(parte.strip()) for parte in valor.split(","))
    except (AttributeError, ValueError):
        raise ValueError(
            "RECORDATORIO_VENTANA_HS debe ser 'min,max' en horas enteras (ej. 24,48)"
        ) from None
    if minimo <= 0 or maximo <= 0 or minimo >= maximo:
        raise ValueError(
            "RECORDATORIO_VENTANA_HS requiere 0 < min < max en horas (ej. 24,48)"
        )
    return minimo, maximo


def texto_recordatorio(
    *,
    paciente: str,
    profesional: str,
    inicio: datetime,
    tz: ZoneInfo,
    direccion: str = "",
) -> str:
    """Arma el mensaje copiable: paciente, profesional, fecha/hora local y dirección."""
    local = a_zona_local(inicio, tz)
    lineas = [
        f"Hola {paciente}, te recordamos tu turno con {profesional} "
        f"el {local.strftime(_FORMATO_FECHA)} a las {local.strftime(_FORMATO_HORA)}."
    ]
    limpia = direccion.strip()
    if limpia:
        lineas.append(f"Dirección: {limpia}")
    return "\n".join(lineas)


__all__ = ["parse_ventana", "texto_recordatorio"]
