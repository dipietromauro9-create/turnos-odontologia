"""Tests de configuración por entorno (spec backend-base: config carga desde entorno)."""

from __future__ import annotations

import logging
import os

import pytest

BASE_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+psycopg://turnos:secreto@localhost:5432/turnos",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "x" * 40,
    "ACCESS_MINUTES": "15",
    "REFRESH_DAYS": "7",
    "TENANT_DEFAULT_SLUG": "demo",
    "TZ": "America/Argentina/Buenos_Aires",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "RECORDATORIO_VENTANA_HS": "24,48",
}


def _con_env(monkeypatch: pytest.MonkeyPatch, extra: dict[str, str] | None = None) -> None:
    for key in list(BASE_ENV.keys()) + ["SECRET_KEY"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(os, "environ", {**BASE_ENV, **(extra or {})})


def test_arranca_con_env_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_env(monkeypatch)
    from app.core.settings import Settings

    settings = Settings()
    assert settings.tenant_default_slug == "demo"
    assert settings.tz == "America/Argentina/Buenos_Aires"
    assert settings.access_minutes == 15


def test_falla_rapido_nombrando_variable_faltante(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.core.settings import Settings

    with pytest.raises(Exception, match="DATABASE_URL"):
        Settings()


def test_secret_key_corta_se_rechaza(monkeypatch: pytest.MonkeyPatch) -> None:
    _con_env(monkeypatch, {"SECRET_KEY": "corta"})
    from app.core.settings import Settings

    with pytest.raises(Exception, match="SECRET_KEY"):
        Settings()


def test_nunca_loguea_secretos(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _con_env(monkeypatch)
    from app.core.settings import get_settings

    with caplog.at_level(logging.INFO):
        settings = get_settings()
        settings.log_safe()
    assert settings.secret_key not in caplog.text
    assert "DATABASE_URL" not in caplog.text or "secreto" not in caplog.text


def test_tz_por_defecto_es_buenos_aires(monkeypatch: pytest.MonkeyPatch) -> None:
    env = dict(BASE_ENV)
    del env["TZ"]
    _con_env(monkeypatch)
    monkeypatch.delenv("TZ", raising=False)
    # Simula ausencia de TZ: el default del modelo debe aplicar
    import importlib

    import app.core.settings as mod

    monkeypatch.setattr(os, "environ", {k: v for k, v in BASE_ENV.items() if k != "TZ"})
    importlib.reload(mod)
    assert mod.Settings().tz == "America/Argentina/Buenos_Aires"
    importlib.reload(mod)
