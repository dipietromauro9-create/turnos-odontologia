"""Estado efímero de seguridad: lockout, cuota por IP+email y blacklist de `jti`."""

from __future__ import annotations

import hashlib
import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from redis import Redis

from app.core.settings import get_settings

MAX_FALLOS = 10
VENTANA_FALLOS_SEGUNDOS = 15 * 60
VENTANA_BLOQUEO_SEGUNDOS = 15 * 60
LIMITE_CUOTA = 5
VENTANA_CUOTA_SEGUNDOS = 60

PREFIJO_FALLOS = "auth:fallos"
PREFIJO_BLOQUEO = "auth:bloqueo"
PREFIJO_TASA = "auth:tasa"
PREFIJO_REVOCADO = "auth:revocado"


@dataclass(frozen=True)
class BloqueoInfo:
    """Resultado de consultar un bloqueo; `reintentar_en` son segundos restantes."""

    bloqueado: bool
    reintentar_en: int = 0

    def __bool__(self) -> bool:
        return self.bloqueado


@dataclass(frozen=True)
class CuotaInfo:
    """Resultado de consumir cuota; `reintentar_en` son segundos restantes."""

    permitido: bool
    reintentar_en: int = 0

    def __bool__(self) -> bool:
        return self.permitido


class TokenStore(Protocol):
    """Operaciones de estado efímero que el servicio de auth necesita."""

    def registrar_fallo(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None: ...

    def esta_bloqueado(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> BloqueoInfo: ...

    def limpiar_fallos(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None: ...

    def consumir_cuota(self, ip: str, email: str) -> CuotaInfo: ...

    def revocar(self, jti: str, ttl_segundos: int) -> bool: ...

    def esta_revocado(self, jti: str) -> bool: ...


def _hash_email(email: str) -> str:
    """R9: nunca guardar el email en claro en las claves; citext lo normaliza."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _clave_fallos(tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> str:
    return f"{PREFIJO_FALLOS}:{tenant_id}:{usuario_id}"


def _clave_bloqueo(tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> str:
    return f"{PREFIJO_BLOQUEO}:{tenant_id}:{usuario_id}"


def _clave_tasa(ip: str, email: str) -> str:
    return f"{PREFIJO_TASA}:{ip}:{_hash_email(email)}"


def _clave_revocado(jti: str) -> str:
    return f"{PREFIJO_REVOCADO}:{jti}"


class InMemoryTokenStore:
    """Implementación con reloj inyectable para tests unitarios."""

    def __init__(
        self,
        reloj: Callable[[], float] | None = None,
    ) -> None:
        self._reloj = reloj or time.monotonic
        self._fallos: dict[tuple[uuid.UUID, uuid.UUID], tuple[int, float]] = {}
        self._bloqueos: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        self._cuotas: dict[tuple[str, str], tuple[int, float]] = {}
        self._revocados: dict[str, float] = {}

    def registrar_fallo(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        clave = (tenant_id, usuario_id)
        ahora = self._reloj()
        actual = self._fallos.get(clave)
        if actual is None or actual[1] <= ahora:
            conteo, expira = 1, ahora + VENTANA_FALLOS_SEGUNDOS
        else:
            conteo, expira = actual[0] + 1, actual[1]
        self._fallos[clave] = (conteo, expira)
        if conteo >= MAX_FALLOS:
            self._bloqueos[clave] = ahora + VENTANA_BLOQUEO_SEGUNDOS

    def esta_bloqueado(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> BloqueoInfo:
        clave = (tenant_id, usuario_id)
        ahora = self._reloj()
        expira = self._bloqueos.get(clave)
        if expira is None or expira <= ahora:
            self._bloqueos.pop(clave, None)
            return BloqueoInfo(bloqueado=False)
        return BloqueoInfo(bloqueado=True, reintentar_en=math.ceil(expira - ahora))

    def limpiar_fallos(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        clave = (tenant_id, usuario_id)
        self._fallos.pop(clave, None)
        self._bloqueos.pop(clave, None)

    def consumir_cuota(self, ip: str, email: str) -> CuotaInfo:
        clave = (ip, _hash_email(email))
        ahora = self._reloj()
        actual = self._cuotas.get(clave)
        if actual is None or actual[1] <= ahora:
            conteo, expira = 1, ahora + VENTANA_CUOTA_SEGUNDOS
        else:
            conteo, expira = actual[0] + 1, actual[1]
        self._cuotas[clave] = (conteo, expira)
        if conteo <= LIMITE_CUOTA:
            return CuotaInfo(permitido=True)
        return CuotaInfo(permitido=False, reintentar_en=max(1, math.ceil(expira - ahora)))

    def revocar(self, jti: str, ttl_segundos: int) -> bool:
        ahora = self._reloj()
        expira = self._revocados.get(jti)
        if expira is not None and expira > ahora:
            return False
        self._revocados[jti] = ahora + max(ttl_segundos, 1)
        return True

    def esta_revocado(self, jti: str) -> bool:
        ahora = self._reloj()
        expira = self._revocados.get(jti)
        if expira is None:
            return False
        if expira <= ahora:
            self._revocados.pop(jti, None)
            return False
        return True


class RedisTokenStore:
    """Implementación de runtime: contadores con TTL y `SET NX EX` en Redis."""

    def __init__(self, *, client: Redis | None = None, url: str | None = None) -> None:
        if client is not None:
            self._redis = client
        else:
            destino = url or get_settings().redis_url
            self._redis = Redis.from_url(destino, decode_responses=True)

    def registrar_fallo(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        clave = _clave_fallos(tenant_id, usuario_id)
        conteo = int(self._redis.incr(clave))
        if conteo == 1:
            self._redis.expire(clave, VENTANA_FALLOS_SEGUNDOS)
        if conteo >= MAX_FALLOS:
            self._redis.set(
                _clave_bloqueo(tenant_id, usuario_id),
                "1",
                ex=VENTANA_BLOQUEO_SEGUNDOS,
            )

    def esta_bloqueado(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> BloqueoInfo:
        ttl = int(self._redis.ttl(_clave_bloqueo(tenant_id, usuario_id)))
        if ttl <= 0:
            return BloqueoInfo(bloqueado=False)
        return BloqueoInfo(bloqueado=True, reintentar_en=ttl)

    def limpiar_fallos(self, tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        self._redis.delete(
            _clave_fallos(tenant_id, usuario_id),
            _clave_bloqueo(tenant_id, usuario_id),
        )

    def consumir_cuota(self, ip: str, email: str) -> CuotaInfo:
        clave = _clave_tasa(ip, email)
        conteo = int(self._redis.incr(clave))
        if conteo == 1:
            self._redis.expire(clave, VENTANA_CUOTA_SEGUNDOS)
        if conteo <= LIMITE_CUOTA:
            return CuotaInfo(permitido=True)
        ttl = int(self._redis.ttl(clave))
        return CuotaInfo(permitido=False, reintentar_en=max(ttl, 1))

    def revocar(self, jti: str, ttl_segundos: int) -> bool:
        return bool(
            self._redis.set(
                _clave_revocado(jti),
                "1",
                nx=True,
                ex=max(int(ttl_segundos), 1),
            )
        )

    def esta_revocado(self, jti: str) -> bool:
        return bool(self._redis.exists(_clave_revocado(jti)))
