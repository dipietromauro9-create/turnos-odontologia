"""Guardias de arquitectura: dominio sin SQL crudo y modelos con frontera de tenant."""

from __future__ import annotations

import re
from pathlib import Path

from app.db.base import Base
from app.db.models import Tenant, TenantMixin

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"
SQL_CRUDO = re.compile(r"\btext\s*\(")
BULK = re.compile(r"\bbulk_")


def _fuentes_de_dominio() -> list[Path]:
    return sorted(DOMAIN_DIR.rglob("*.py"))


def test_app_domain_no_usa_sql_crudo_ni_bulk() -> None:
    archivos = _fuentes_de_dominio()
    assert archivos, "app/domain debe existir y contener código de dominio"

    infracciones: list[str] = []
    for archivo in archivos:
        fuente = archivo.read_text(encoding="utf-8")
        if SQL_CRUDO.search(fuente) or BULK.search(fuente):
            infracciones.append(str(archivo.relative_to(DOMAIN_DIR)))
    assert infracciones == []


def test_todo_modelo_de_dominio_usa_tenant_mixin() -> None:
    modelos = {mapper.class_ for mapper in Base.registry.mappers}
    dominio = modelos - {Tenant}

    assert dominio, "debe haber al menos un modelo de dominio además de Tenant"
    sin_mixin = sorted(modelo.__name__ for modelo in dominio if not issubclass(modelo, TenantMixin))
    assert sin_mixin == []
