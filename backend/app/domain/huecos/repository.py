"""Consultas de lectura tenant-scoped para el motor de huecos (R3).

Cada consulta declara `tenant_id` de forma explícita además del filtro
automático de `TenantSession`; el paquete es de solo lectura y nunca escribe
turnos ni ninguna otra tabla.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import or_, select

from app.db.models import Bloqueo, Disponibilidad, EstadoTurno, Prestacion, Profesional, Turno
from app.db.session import TenantSession


class HuecosRepository:
    """Acceso de solo lectura a las fuentes que alimentan el cálculo."""

    def __init__(self, session: TenantSession) -> None:
        self._session = session

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._session.tenant_id

    def obtener_profesional(self, profesional_id: uuid.UUID) -> Profesional | None:
        return self._session.execute(
            select(Profesional).where(
                Profesional.tenant_id == self.tenant_id,
                Profesional.id == profesional_id,
            )
        ).scalar_one_or_none()

    def obtener_prestacion(self, prestacion_id: uuid.UUID) -> Prestacion | None:
        return self._session.execute(
            select(Prestacion).where(
                Prestacion.tenant_id == self.tenant_id,
                Prestacion.id == prestacion_id,
            )
        ).scalar_one_or_none()

    def franjas(
        self,
        profesional_id: uuid.UUID,
        dias: Collection[int],
    ) -> list[Disponibilidad]:
        if not dias:
            return []
        consulta = (
            select(Disponibilidad)
            .where(
                Disponibilidad.tenant_id == self.tenant_id,
                Disponibilidad.profesional_id == profesional_id,
                Disponibilidad.dia_semana.in_(dias),
            )
            .order_by(Disponibilidad.dia_semana, Disponibilidad.hora_desde)
        )
        return list(self._session.execute(consulta).scalars())

    def bloqueos(
        self,
        profesional_id: uuid.UUID,
        desde: datetime,
        hasta: datetime,
    ) -> list[Bloqueo]:
        consulta = (
            select(Bloqueo)
            .where(
                Bloqueo.tenant_id == self.tenant_id,
                or_(
                    Bloqueo.profesional_id == profesional_id,
                    Bloqueo.profesional_id.is_(None),
                ),
                Bloqueo.desde < hasta,
                Bloqueo.hasta > desde,
            )
            .order_by(Bloqueo.desde, Bloqueo.id)
        )
        return list(self._session.execute(consulta).scalars())

    def turnos(
        self,
        profesional_id: uuid.UUID,
        desde: datetime,
        hasta: datetime,
    ) -> list[Turno]:
        consulta = (
            select(Turno)
            .where(
                Turno.tenant_id == self.tenant_id,
                Turno.profesional_id == profesional_id,
                Turno.estado != EstadoTurno.CANCELADO,
                Turno.inicio < hasta,
                Turno.fin > desde,
            )
            .order_by(Turno.inicio, Turno.id)
        )
        return list(self._session.execute(consulta).scalars())
