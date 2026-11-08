"""Entrada del worker RQ: consume la cola `default`.

El servicio `worker` de Compose reutiliza la imagen de `api` con este comando.
El cron de recordatorios lo agenda el servicio `scheduler` (proceso aparte,
porque rq-scheduler necesita el hilo principal para sus señales).
"""

from __future__ import annotations

import os
import sys

import redis
from rq import Queue, Worker


def chequear_redis(redis_url: str) -> None:
    cliente = redis.Redis.from_url(redis_url, socket_connect_timeout=10)
    cliente.ping()


def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    chequear_redis(redis_url)
    conexion = redis.Redis.from_url(redis_url)
    cola = Queue("default", connection=conexion)
    print(f"[worker] conectado a {redis_url}; escuchando cola 'default'", flush=True)
    Worker([cola], connection=cola.connection).work()


if __name__ == "__main__":
    sys.exit(main())
