"""Health público con indicador de DB (spec backend-base: liveness)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "z" * 40)
    monkeypatch.setenv("ACCESS_MINUTES", "15")
    monkeypatch.setenv("REFRESH_DAYS", "7")
    monkeypatch.setenv("TENANT_DEFAULT_SLUG", "demo")
    monkeypatch.setenv("TZ", "America/Argentina/Buenos_Aires")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("RECORDATORIO_VENTANA_HS", "24,48")
    from app.core.settings import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_health_devuelve_ok_sin_auth(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "database" in body


def test_health_es_publico_sin_401_403(client: TestClient) -> None:
    resp = client.get("/health", headers={"Authorization": ""})
    assert resp.status_code not in (401, 403)
