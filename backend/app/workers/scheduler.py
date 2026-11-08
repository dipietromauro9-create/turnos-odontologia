"""Proceso del scheduler: registra el cron horario y encola los jobs vencidos.

Va separado del `worker` porque `rq-scheduler` instala manejadores de señales y
solo puede correr en el hilo principal de un proceso.
"""

from __future__ import annotations

import os
import sys

import redis
from rq import Queue
from rq_scheduler import Scheduler

CRON_RECORDATORIOS = "0 * * * *"
JOB_ID_RECORDATORIOS = "generar_recordatorios_hourly"
JOB_RECORDATORIOS = "app.workers.jobs.generar_recordatorios"


def chequear_redis(redis_url: str) -> None:
    cliente = redis.Redis.from_url(redis_url, socket_connect_timeout=10)
    cliente.ping()


def agendar_recordatorios(scheduler: Scheduler) -> None:
    """Cron horario con `id` fijo: reiniciar el scheduler reemplaza, no acumula."""
    scheduler.cron(
        CRON_RECORDATORIOS,
        JOB_RECORDATORIOS,
        id=JOB_ID_RECORDATORIOS,
        queue_name="default",
    )


def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    chequear_redis(redis_url)
    conexion = redis.Redis.from_url(redis_url)
    Queue("default", connection=conexion)
    scheduler = Scheduler(queue_name="default", connection=conexion)
    agendar_recordatorios(scheduler)
    print(f"[scheduler] conectado a {redis_url}; cron horario de recordatorios", flush=True)
    scheduler.run()


if __name__ == "__main__":
    sys.exit(main())
