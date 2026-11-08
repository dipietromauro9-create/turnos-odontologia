"""Ventana de recordatorios y plantilla del mensaje (RN-CO-02, RN-GL-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.settings import Settings, get_settings
from app.domain.recordatorios.plantilla import parse_ventana, texto_recordatorio

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def test_parsea_la_ventana_por_defecto() -> None:
    assert parse_ventana("24,48") == (24, 48)


@pytest.mark.parametrize("valor", ["12,36", "1,2", " 24 , 48 "])
def test_parsea_ventanas_validas(valor: str) -> None:
    minimo, maximo = parse_ventana(valor)
    assert 0 < minimo < maximo


@pytest.mark.parametrize(
    "valor",
    ["", "24", "24,48,72", "abc,48", "24,abc", "48,24", "24,24", "0,48", "-1,48", "24,-48"],
)
def test_ventanas_invalidas_fallan_con_mensaje_explicito(valor: str) -> None:
    with pytest.raises(ValueError, match="RECORDATORIO_VENTANA_HS"):
        parse_ventana(valor)


def test_texto_incluye_datos_del_turno() -> None:
    inicio = datetime(2030, 6, 3, 13, 0, tzinfo=UTC)
    texto = texto_recordatorio(
        paciente="Paciente Ficticio",
        profesional="Profesional Ficticio",
        inicio=inicio,
        tz=TZ,
        direccion="Av. Ficticia 123",
    )
    assert "Paciente Ficticio" in texto
    assert "Profesional Ficticio" in texto
    assert "03/06/2030" in texto
    assert "10:00" in texto
    assert "Av. Ficticia 123" in texto


def test_texto_muestra_la_hora_local_y_no_la_utc() -> None:
    inicio = datetime(2030, 6, 3, 13, 0, tzinfo=UTC)
    texto = texto_recordatorio(
        paciente="Paciente Ficticio",
        profesional="Profesional Ficticio",
        inicio=inicio,
        tz=TZ,
        direccion="",
    )
    assert "10:00" in texto and "13:00" not in texto


def test_direccion_vacia_omite_la_linea() -> None:
    texto = texto_recordatorio(
        paciente="Paciente Ficticio",
        profesional="Profesional Ficticio",
        inicio=datetime(2030, 6, 3, 13, 0, tzinfo=UTC),
        tz=TZ,
        direccion="   ",
    )
    assert "Dirección" not in texto and "None" not in texto


def test_texto_es_determinista_y_conserva_acentos() -> None:
    argumentos = dict(
        paciente="Ñandú Pérez",
        profesional="Dra. Muñoz",
        inicio=datetime(2030, 12, 31, 23, 30, tzinfo=UTC),
        tz=TZ,
        direccion="Calle Ñ 45",
    )
    primero = texto_recordatorio(**argumentos)
    segundo = texto_recordatorio(**argumentos)
    assert primero == segundo
    assert "Ñandú Pérez" in primero and "Muñoz" in primero
    assert "31/12/2030" in primero and "20:30" in primero


def test_settings_expone_la_direccion_del_consultorio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "t" * 40)
    monkeypatch.setenv("ACCESS_MINUTES", "15")
    monkeypatch.setenv("REFRESH_DAYS", "7")
    monkeypatch.setenv("TENANT_DEFAULT_SLUG", "demo")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("RECORDATORIO_VENTANA_HS", "24,48")
    monkeypatch.setenv("CONSULTORIO_DIRECCION", "Av. Ficticia 123")
    get_settings.cache_clear()
    try:
        assert Settings().consultorio_direccion == "Av. Ficticia 123"
    finally:
        get_settings.cache_clear()
