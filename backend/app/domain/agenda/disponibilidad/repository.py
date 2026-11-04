"""Consultas de disponibilidad siempre sobre la TenantSession del UoW."""

import uuid
from datetime import time

from sqlalchemy import select

from app.db.models import Disponibilidad
from app.db.session import TenantSession
from app.domain.persistence import BaseRepository


class DisponibilidadRepository(BaseRepository[Disponibilidad]):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session, Disponibilidad)

    def intersecta(self, profesional_id: uuid.UUID, dia: int, desde: time, hasta: time) -> bool:
        consulta = (
            select(Disponibilidad.id)
            .where(
                Disponibilidad.profesional_id == profesional_id,
                Disponibilidad.dia_semana == dia,
                Disponibilidad.hora_desde < hasta,
                desde < Disponibilidad.hora_hasta,
            )
            .limit(1)
        )
        return self._session.execute(consulta).first() is not None

    def listar(self, profesional_id: uuid.UUID | None) -> list[Disponibilidad]:
        consulta = select(Disponibilidad)
        if profesional_id is not None:
            consulta = consulta.where(Disponibilidad.profesional_id == profesional_id)
        return list(
            self._session.execute(
                consulta.order_by(Disponibilidad.dia_semana, Disponibilidad.hora_desde)
            ).scalars()
        )
