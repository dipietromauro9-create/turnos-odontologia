"""Rate limiting de las rutas públicas del turnero (10 req/min por IP).

El runtime usa Redis; si no está disponible cae a memoria para no tumbar el
canal público en desarrollo o tests. La cuota se cuenta por IP y ventana fija.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.core.settings import get_settings

LIMITE_POR_MINUTO = 10
VENTANA_SEGUNDOS = 60
PREFIJO = "turnero:tasa"


@dataclass(frozen=True)
class CuotaPublica:
    """Resultado de consumir una cuota; `reintentar_en` son segundos restantes."""

    permitido: bool
    reintentar_en: int = 0


class RateLimiter(Protocol):
    """Contrato mínimo que consume la dependency del router público."""

    def consumir(self, clave: str) -> CuotaPublica: ...


class InMemoryRateLimiter:
    """Contador por proceso con reloj inyectable (tests y fallback)."""

    def __init__(
        self,
        *,
        limite: int = LIMITE_POR_MINUTO,
        ventana: int = VENTANA_SEGUNDOS,
        reloj: Callable[[], float] | None = None,
    ) -> None:
        self._limite = limite
        self._ventana = ventana
        self._reloj = reloj or time.monotonic
        self._cuotas: dict[str, tuple[int, float]] = {}

    def consumir(self, clave: str) -> CuotaPublica:
        ahora = self._reloj()
        actual = self._cuotas.get(clave)
        if actual is None or actual[1] <= ahora:
            conteo, expira = 1, ahora + self._ventana
        else:
            conteo, expira = actual[0] + 1, actual[1]
        self._cuotas[clave] = (conteo, expira)
        if conteo <= self._limite:
            return CuotaPublica(permitido=True)
        return CuotaPublica(
            permitido=False,
            reintentar_en=max(1, math.ceil(expira - ahora)),
        )


class RedisRateLimiter:
    """Contador compartido entre workers con `INCR` + `EXPIRE`."""

    def __init__(
        self,
        *,
        client: Redis | None = None,
        url: str | None = None,
        limite: int = LIMITE_POR_MINUTO,
        ventana: int = VENTANA_SEGUNDOS,
    ) -> None:
        self._redis = client or Redis.from_url(
            url or get_settings().redis_url,
            decode_responses=True,
        )
        self._limite = limite
        self._ventana = ventana

    def consumir(self, clave: str) -> CuotaPublica:
        llave = f"{PREFIJO}:{clave}"
        conteo = int(self._redis.incr(llave))
        if conteo == 1:
            self._redis.expire(llave, self._ventana)
        if conteo <= self._limite:
            return CuotaPublica(permitido=True)
        ttl = int(self._redis.ttl(llave))
        return CuotaPublica(permitido=False, reintentar_en=max(ttl, 1))


class RateLimiterConFallback:
    """Redis como backend principal; memoria si la conexión falla."""

    def __init__(
        self,
        principal: RateLimiter | None = None,
        *,
        limite: int = LIMITE_POR_MINUTO,
        ventana: int = VENTANA_SEGUNDOS,
    ) -> None:
        self._principal = principal or RedisRateLimiter(limite=limite, ventana=ventana)
        self._limite = limite
        self._ventana = ventana
        self._memoria: RateLimiter | None = None

    def consumir(self, clave: str) -> CuotaPublica:
        if self._memoria is not None:
            return self._memoria.consumir(clave)
        try:
            return self._principal.consumir(clave)
        except RedisError:
            self._memoria = InMemoryRateLimiter(limite=self._limite, ventana=self._ventana)
            return self._memoria.consumir(clave)


@lru_cache(maxsize=1)
def _limiter_singleton() -> RateLimiter:
    return RateLimiterConFallback()


def get_rate_limiter() -> RateLimiter:
    """Dependency de runtime; los tests la sustituyen por memoria."""
    return _limiter_singleton()


__all__ = [
    "CuotaPublica",
    "InMemoryRateLimiter",
    "LIMITE_POR_MINUTO",
    "RateLimiter",
    "RateLimiterConFallback",
    "RedisRateLimiter",
    "VENTANA_SEGUNDOS",
    "get_rate_limiter",
]
