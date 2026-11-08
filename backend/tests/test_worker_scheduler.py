"""Cableado del cron horario: scheduler en proceso propio + worker consumidor."""

from __future__ import annotations

import pytest

from app.workers import main as worker_main
from app.workers import scheduler as worker_scheduler


class SchedulerFalso:
    """Simula el guardado por `id` de rq-scheduler (mismo id = reemplazo)."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, object]] = {}

    def cron(self, cron_string: str, func: str, **kwargs: object) -> None:
        job_id = str(kwargs["id"])
        self.jobs[job_id] = {"cron": cron_string, "func": func, **kwargs}

    def run(self) -> None:
        self.corriendo = True


def test_agenda_un_unico_cron_horario_idempotente() -> None:
    scheduler = SchedulerFalso()

    worker_scheduler.agendar_recordatorios(scheduler)  # type: ignore[arg-type]
    worker_scheduler.agendar_recordatorios(scheduler)  # type: ignore[arg-type]

    assert list(scheduler.jobs) == ["generar_recordatorios_hourly"]
    job = scheduler.jobs["generar_recordatorios_hourly"]
    assert job["cron"] == "0 * * * *"
    assert job["func"] == "app.workers.jobs.generar_recordatorios"
    assert job["queue_name"] == "default"


def test_el_scheduler_falla_rapido_si_redis_no_responde(monkeypatch: pytest.MonkeyPatch) -> None:
    def _falla(_url: str) -> None:
        raise ConnectionError("redis caído")

    monkeypatch.setattr(worker_scheduler, "chequear_redis", _falla)

    with pytest.raises(ConnectionError):
        worker_scheduler.main()


def test_el_scheduler_agenda_y_entra_en_su_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = SchedulerFalso()

    monkeypatch.setattr(worker_scheduler, "chequear_redis", lambda _url: None)
    monkeypatch.setattr(worker_scheduler, "Queue", lambda *_a, **_k: object())
    monkeypatch.setattr(worker_scheduler, "Scheduler", lambda **_kwargs: scheduler)

    worker_scheduler.main()

    assert list(scheduler.jobs) == ["generar_recordatorios_hourly"]
    assert getattr(scheduler, "corriendo", False) is True


def test_el_worker_consume_la_cola_default(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: dict[str, object] = {}

    class ColaFalsa:
        connection = object()

    class WorkerFalso:
        def __init__(self, colas: list[object], connection: object) -> None:
            llamadas["colas"] = colas
            llamadas["connection"] = connection

        def work(self) -> None:
            llamadas["work"] = True

    monkeypatch.setattr(worker_main, "chequear_redis", lambda _url: None)
    monkeypatch.setattr(worker_main, "Queue", lambda _nombre, connection: ColaFalsa())
    monkeypatch.setattr(worker_main, "Worker", WorkerFalso)

    worker_main.main()

    assert llamadas["work"] is True
    assert len(llamadas["colas"]) == 1  # type: ignore[arg-type]
