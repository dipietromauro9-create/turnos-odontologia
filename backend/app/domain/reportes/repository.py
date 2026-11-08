"""Consultas de solo lectura para reportes (R3: siempre tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select

from app.db.models import (
    Bloqueo,
    Disponibilidad,
    EstadoRecordatorio,
    Profesional,
    Recordatorio,
    Turno,
)
from app.db.session import TenantSession


class ReportesRepository:
    """Carga las fuentes del cálculo en una sola transacción de lectura."""

    def __init__(self, session: TenantSession) -> None:
        self._session = session

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._session.tenant_id

    def profesionales(self, profesional_id: uuid.UUID | None) -> list[Profesional]:
        consulta = select(Profesional).where(Profesional.activo.is_(True))
        if profesional_id is not None:
            consulta = consulta.where(Profesional.id == profesional_id)
        return list(
            self._session.execute(
                consulta.order_by(Profesional.nombre, Profesional.id)
            ).scalars()
        )

    def franjas(self, profesional_ids: list[uuid.UUID]) -> list[Disponibilidad]:
        if not profesional_ids:
            return []
        consulta = (
            select(Disponibilidad)
            .where(Disponibilidad.profesional_id.in_(profesional_ids))
            .order_by(Disponibilidad.profesional_id, Disponibilidad.dia_semana)
        )
        return list(self._session.execute(consulta).scalars())

    def bloqueos(
        self, profesional_ids: list[uuid.UUID], desde: datetime, hasta: datetime
    ) -> list[Bloqueo]:
        if not profesional_ids:
            return []
        consulta = select(Bloqueo).where(
            or_(
                Bloqueo.profesional_id.in_(profesional_ids),
                Bloqueo.profesional_id.is_(None),
            ),
            Bloqueo.desde < hasta,
            Bloqueo.hasta > desde,
        )
        return list(self._session.execute(consulta).scalars())

    def turnos(
        self, profesional_ids: list[uuid.UUID], desde: datetime, hasta: datetime
    ) -> list[Turno]:
        if not profesional_ids:
            return []
        consulta = select(Turno).where(
            Turno.profesional_id.in_(profesional_ids),
            Turno.inicio >= desde,
            Turno.inicio < hasta,
        )
        return list(self._session.execute(consulta).scalars())

    def recordatorios_enviados(
        self, profesional_ids: list[uuid.UUID], desde: datetime, hasta: datetime
    ) -> dict[uuid.UUID, int]:
        if not profesional_ids:
            return {}
        consulta = (
            select(Turno.profesional_id, func.count(Recordatorio.id))
            .join(Recordatorio, Recordatorio.turno_id == Turno.id)
            .where(
                Turno.profesional_id.in_(profesional_ids),
                Turno.inicio >= desde,
                Turno.inicio < hasta,
                Recordatorio.estado == EstadoRecordatorio.ENVIADO,
            )
            .group_by(Turno.profesional_id)
        )
        return {fila[0]: fila[1] for fila in self._session.execute(consulta)}
