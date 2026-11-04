"""Datos exclusivamente ficticios para los tests de agenda (R9)."""

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Bloqueo, Disponibilidad, Profesional, Tenant
from tests.factories import crear_profesional as crear_profesional


def crear_disponibilidad(
    session: Session, tenant: Tenant, profesional: Profesional, **cambios: Any
) -> Disponibilidad:
    datos = {"dia_semana": 0, "hora_desde": time(9), "hora_hasta": time(13)}
    datos.update(cambios)
    fila = Disponibilidad(tenant_id=tenant.id, profesional_id=profesional.id, **datos)
    session.add(fila)
    session.commit()
    return fila


def crear_bloqueo(
    session: Session, tenant: Tenant, profesional: Profesional | None = None, **cambios: Any
) -> Bloqueo:
    desde = datetime(2026, 11, 3, 9, tzinfo=UTC)
    datos = {"desde": desde, "hasta": desde + timedelta(hours=1), "motivo": "Cierre ficticio"}
    datos.update(cambios)
    fila = Bloqueo(
        tenant_id=tenant.id,
        profesional_id=profesional.id if profesional else None,
        **datos,
    )
    session.add(fila)
    session.commit()
    return fila
