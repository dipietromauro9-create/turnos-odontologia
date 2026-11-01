"""Estado efímero de seguridad: lockout, cuota por IP+email y blacklist de `jti`."""

from __future__ import annotations

import time
import uuid

import pytest
import redis

from app.core.token_store import (
    LIMITE_CUOTA,
    MAX_FALLOS,
    VENTANA_BLOQUEO_SEGUNDOS,
    VENTANA_CUOTA_SEGUNDOS,
    InMemoryTokenStore,
    RedisTokenStore,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTRO_TENANT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USUARIO_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
IP = "203.0.113.5"


class RelojFalso:
    def __init__(self) -> None:
        self.ahora = 1_000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


@pytest.fixture()
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture()
def store(reloj: RelojFalso) -> InMemoryTokenStore:
    return InMemoryTokenStore(reloj=reloj)


def _fallar(store: InMemoryTokenStore, veces: int, usuario_id: uuid.UUID = USUARIO_ID) -> None:
    for _ in range(veces):
        store.registrar_fallo(TENANT_ID, usuario_id)


def test_nueve_fallos_no_bloquean_y_el_decimo_si(store: InMemoryTokenStore) -> None:
    _fallar(store, MAX_FALLOS - 1)
    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is False

    store.registrar_fallo(TENANT_ID, USUARIO_ID)

    info = store.esta_bloqueado(TENANT_ID, USUARIO_ID)
    assert info.bloqueado is True
    assert info.reintentar_en > 0
    assert info.reintentar_en <= VENTANA_BLOQUEO_SEGUNDOS


def test_el_bloqueo_sigue_vigente_dentro_de_la_ventana_y_expira(
    store: InMemoryTokenStore, reloj: RelojFalso
) -> None:
    _fallar(store, MAX_FALLOS)
    assert bool(store.esta_bloqueado(TENANT_ID, USUARIO_ID)) is True

    reloj.avanzar(VENTANA_BLOQUEO_SEGUNDOS - 1)
    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is True

    reloj.avanzar(2)
    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is False


def test_un_login_exitoso_reinicia_el_contador(store: InMemoryTokenStore) -> None:
    _fallar(store, MAX_FALLOS - 1)
    store.limpiar_fallos(TENANT_ID, USUARIO_ID)

    _fallar(store, MAX_FALLOS - 1)
    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is False

    store.registrar_fallo(TENANT_ID, USUARIO_ID)
    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is True


def test_los_fallos_de_un_tenant_no_bloquean_a_otro(store: InMemoryTokenStore) -> None:
    _fallar(store, MAX_FALLOS)

    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is True
    assert store.esta_bloqueado(OTRO_TENANT_ID, USUARIO_ID).bloqueado is False


def test_los_fallos_viejos_no_cuentan_para_bloquear(
    store: InMemoryTokenStore, reloj: RelojFalso
) -> None:
    _fallar(store, MAX_FALLOS - 1)

    reloj.avanzar(VENTANA_BLOQUEO_SEGUNDOS + 1)
    _fallar(store, MAX_FALLOS - 1)

    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is False


def test_cuota_acepta_cinco_y_rechaza_el_sexto_con_los_segundos_restantes(
    store: InMemoryTokenStore,
) -> None:
    for _ in range(LIMITE_CUOTA):
        assert store.consumir_cuota(IP, "dueno@demo").permitido is True

    rechazo = store.consumir_cuota(IP, "dueno@demo")

    assert rechazo.permitido is False
    assert 0 < rechazo.reintentar_en <= VENTANA_CUOTA_SEGUNDOS


def test_la_cuota_es_por_ip_y_email_sin_afectar_a_otro_email(store: InMemoryTokenStore) -> None:
    for _ in range(LIMITE_CUOTA + 1):
        store.consumir_cuota(IP, "recepcion@demo")

    assert store.consumir_cuota(IP, "dueno@demo").permitido is True
    assert store.consumir_cuota("198.51.100.7", "recepcion@demo").permitido is True


def test_la_cuota_se_renueva_al_terminar_la_ventana(
    store: InMemoryTokenStore, reloj: RelojFalso
) -> None:
    for _ in range(LIMITE_CUOTA):
        store.consumir_cuota(IP, "dueno@demo")
    assert store.consumir_cuota(IP, "dueno@demo").permitido is False

    reloj.avanzar(VENTANA_CUOTA_SEGUNDOS + 1)

    assert store.consumir_cuota(IP, "dueno@demo").permitido is True


def test_revocar_y_esta_revocado_respetan_el_ttl(
    store: InMemoryTokenStore, reloj: RelojFalso
) -> None:
    jti = str(uuid.uuid4())

    assert store.revocar(jti, 30) is True
    assert store.esta_revocado(jti) is True

    reloj.avanzar(31)

    assert store.esta_revocado(jti) is False


def test_revocar_el_mismo_jti_dos_veces_falla_la_segunda(store: InMemoryTokenStore) -> None:
    jti = str(uuid.uuid4())

    assert store.revocar(jti, 60) is True
    assert store.revocar(jti, 60) is False
    assert store.esta_revocado(jti) is True


@pytest.mark.integration
def test_redis_revocar_respeta_el_ttl_y_set_nx_falla_el_segundo_intento(
    redis_client: redis.Redis, redis_url: str
) -> None:
    store = RedisTokenStore(url=redis_url)
    jti = f"integracion-{uuid.uuid4()}"

    assert store.revocar(jti, 1) is True
    assert store.esta_revocado(jti) is True
    assert store.revocar(jti, 1) is False

    time.sleep(1.2)

    assert store.esta_revocado(jti) is False


@pytest.mark.integration
def test_redis_el_bloqueo_tiene_el_ttl_de_la_ventana(
    redis_client: redis.Redis, redis_url: str
) -> None:
    store = RedisTokenStore(url=redis_url)
    for _ in range(MAX_FALLOS):
        store.registrar_fallo(TENANT_ID, USUARIO_ID)

    info = store.esta_bloqueado(TENANT_ID, USUARIO_ID)

    assert info.bloqueado is True
    assert 0 < info.reintentar_en <= VENTANA_BLOQUEO_SEGUNDOS


@pytest.mark.integration
def test_redis_la_ventana_de_fallos_expira_y_reinicia_el_contador(
    redis_client: redis.Redis, redis_url: str
) -> None:
    store = RedisTokenStore(url=redis_url)
    for _ in range(MAX_FALLOS - 1):
        store.registrar_fallo(TENANT_ID, USUARIO_ID)

    claves = list(redis_client.scan_iter("auth:fallos:*"))
    assert len(claves) == 1
    redis_client.expire(claves[0], 1)

    time.sleep(1.2)
    store.registrar_fallo(TENANT_ID, USUARIO_ID)

    assert store.esta_bloqueado(TENANT_ID, USUARIO_ID).bloqueado is False
    assert int(redis_client.get(claves[0])) == 1
