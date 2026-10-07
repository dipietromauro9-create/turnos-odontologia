"""Entrada del worker RQ (+ chequeo de conexión a Redis y al scheduler).

El servicio `worker` de Compose reutiliza la imagen de api con este comando.
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
    # rq-scheduler se cablea en C-11; acá solo validamos que el paquete importa.
    import rq_scheduler  # noqa: F401

    print(f"[worker] conectado a {redis_url}; escuchando cola 'default'", flush=True)
    cola = Queue("default", connection=redis.Redis.from_url(redis_url))
    worker = Worker([cola], connection=cola.connection)
    worker.work()


if __name__ == "__main__":
    sys.exit(main())
