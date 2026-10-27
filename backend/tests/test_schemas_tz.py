"""Bordes de aplicación: timestamps aware obligatorios y rechazo de campos extra (R1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.tenancy.schemas import UsuarioOut


def _payload(**overrides: object) -> dict[str, object]:
    ahora = datetime.now(UTC)
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "nombre": "Persona Ficticia",
        "email": "persona@demo",
        "rol": "recepcion",
        "es_dueno": False,
        "activo": True,
        "creado_en": ahora,
        "actualizado_en": ahora,
    }
    base.update(overrides)
    return base


def test_schema_acepta_datetimes_aware() -> None:
    usuario = UsuarioOut(**_payload())
    assert usuario.creado_en.tzinfo is not None


def test_schema_rechaza_datetime_naive() -> None:
    with pytest.raises(ValidationError):
        UsuarioOut(**_payload(creado_en=datetime(2026, 1, 1, 12, 0, 0)))


def test_schema_rechaza_campos_extra() -> None:
    with pytest.raises(ValidationError):
        UsuarioOut(**_payload(campo_no_declarado="x"))
