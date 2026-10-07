"""Configuración por entorno (Pydantic Settings, R1: extra='forbid')."""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toda la config de runtime viene del entorno; falla rápido si falta algo."""

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    secret_key: str = Field(alias="SECRET_KEY", min_length=32)
    access_minutes: int = Field(alias="ACCESS_MINUTES", gt=0)
    refresh_days: int = Field(alias="REFRESH_DAYS", gt=0)
    tenant_default_slug: str = Field(alias="TENANT_DEFAULT_SLUG", min_length=1)
    tz: str = Field(alias="TZ", default="America/Argentina/Buenos_Aires")
    frontend_origin: str = Field(alias="FRONTEND_ORIGIN")
    recordatorio_ventana_hs: str = Field(alias="RECORDATORIO_VENTANA_HS")

    @field_validator("secret_key")
    @classmethod
    def _secret_largo(cls, value: str) -> str:
        if len(value) < 32:
            msg = "SECRET_KEY debe tener al menos 32 caracteres"
            raise ValueError(msg)
        return value

    def log_safe(self) -> None:
        """Loguea la config sin secretos (R9: jamás exponer SECRET_KEY ni credenciales)."""
        logger = logging.getLogger("turnos.settings")
        logger.info(
            "config access=%s refresh=%s tenant=%s tz=%s frontend=%s ventana=%s",
            self.access_minutes,
            self.refresh_days,
            self.tenant_default_slug,
            self.tz,
            self.frontend_origin,
            self.recordatorio_ventana_hs,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
