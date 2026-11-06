"""Consultas tenant-scoped para el servicio de turnos."""

import uuid
from datetime import datetime

from sqlalchemy import or_, select

from app.db.models import Bloqueo, Disponibilidad, EstadoTurno, Turno
from app.db.session import TenantSession
from app.domain.persistence import BaseRepository
from app.domain.turnos.schemas import TurnoFiltros


class TurnosRepository(BaseRepository[Turno]):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session, Turno)

    def obtener_bloqueado(self, identificador: uuid.UUID) -> Turno | None:
        return self._session.execute(
            select(Turno)
            .where(
                Turno.tenant_id == self.tenant_id,
                Turno.id == identificador,
            )
            .with_for_update()
        ).scalar_one_or_none()

    def por_codigo(self, codigo: str, *, bloquear: bool = False) -> Turno | None:
        """Busca por `codigo_publico` dentro del tenant resuelto (RN-TU-06)."""
        consulta = select(Turno).where(
            Turno.tenant_id == self.tenant_id,
            Turno.codigo_publico == codigo,
        )
        if bloquear:
            consulta = consulta.with_for_update()
        return self._session.execute(consulta).scalar_one_or_none()

    def consultar(self, filtros: TurnoFiltros, profesional_id: uuid.UUID | None) -> list[Turno]:
        consulta = select(Turno).where(Turno.tenant_id == self.tenant_id)
        if profesional_id is not None:
            consulta = consulta.where(Turno.profesional_id == profesional_id)
        if filtros.estado is not None:
            consulta = consulta.where(Turno.estado == filtros.estado)
        if filtros.desde is not None:
            consulta = consulta.where(Turno.inicio >= filtros.desde)
        if filtros.hasta is not None:
            consulta = consulta.where(Turno.inicio < filtros.hasta)
        return list(
            self._session.execute(
                consulta.order_by(Turno.inicio, Turno.id)
                .limit(filtros.limit)
                .offset(filtros.offset)
            ).scalars()
        )

    def franjas(self, profesional_id: uuid.UUID, dia: int) -> list[Disponibilidad]:
        return list(
            self._session.execute(
                select(Disponibilidad)
                .where(
                    Disponibilidad.tenant_id == self.tenant_id,
                    Disponibilidad.profesional_id == profesional_id,
                    Disponibilidad.dia_semana == dia,
                )
                .order_by(Disponibilidad.hora_desde)
            ).scalars()
        )

    def bloqueado(self, profesional_id: uuid.UUID, inicio: datetime, fin: datetime) -> bool:
        return (
            self._session.execute(
                select(Bloqueo.id)
                .where(
                    Bloqueo.tenant_id == self.tenant_id,
                    or_(Bloqueo.profesional_id == profesional_id, Bloqueo.profesional_id.is_(None)),
                    Bloqueo.desde < fin,
                    Bloqueo.hasta > inicio,
                )
                .limit(1)
            ).first()
            is not None
        )

    def ocupado(
        self,
        profesional_id: uuid.UUID,
        inicio: datetime,
        fin: datetime,
        excluir: uuid.UUID | None = None,
    ) -> bool:
        consulta = select(Turno.id).where(
            Turno.tenant_id == self.tenant_id,
            Turno.profesional_id == profesional_id,
            Turno.estado != EstadoTurno.CANCELADO,
            Turno.inicio < fin,
            Turno.fin > inicio,
        )
        if excluir is not None:
            consulta = consulta.where(Turno.id != excluir)
        return self._session.execute(consulta.limit(1)).first() is not None
