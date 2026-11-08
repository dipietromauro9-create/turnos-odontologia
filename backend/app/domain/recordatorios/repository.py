"""Consultas tenant-scoped de recordatorios y candidatos a generar."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.db.models import (
    EstadoRecordatorio,
    EstadoTurno,
    Paciente,
    Profesional,
    Recordatorio,
    Turno,
)
from app.db.session import TenantSession
from app.domain.persistence import BaseRepository


@dataclass(frozen=True)
class Candidato:
    """Turno confirmado sin recordatorio, con lo mínimo para armar el mensaje."""

    turno_id: uuid.UUID
    inicio: datetime
    paciente: str
    profesional: str


class RecordatoriosRepository(BaseRepository[Recordatorio]):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session, Recordatorio)

    def candidatos(
        self,
        *,
        ahora: datetime,
        desde: datetime,
        hasta: datetime,
        antiguedad_maxima: datetime,
    ) -> list[Candidato]:
        """Ventana [desde, hasta] + recuperación de turnos que ya deberían tener aviso."""
        sin_recordatorio = ~(
            select(Recordatorio.id).where(Recordatorio.turno_id == Turno.id).exists()
        )
        ventana = and_(Turno.inicio >= desde, Turno.inicio <= hasta)
        recuperacion = and_(
            Turno.inicio > ahora,
            Turno.inicio < desde,
            Turno.creado_en <= antiguedad_maxima,
        )
        consulta = (
            select(Turno.id, Turno.inicio, Paciente.nombre, Profesional.nombre)
            .join(Paciente, Paciente.id == Turno.paciente_id)
            .join(Profesional, Profesional.id == Turno.profesional_id)
            .where(
                Turno.estado == EstadoTurno.CONFIRMADO,
                or_(ventana, recuperacion),
                sin_recordatorio,
            )
            .order_by(Turno.inicio, Turno.id)
        )
        return [Candidato(*fila) for fila in self._session.execute(consulta)]

    def en_cola(
        self, profesional_id: uuid.UUID | None
    ) -> list[tuple[Recordatorio, datetime, str, str]]:
        """Pendientes y fallidos de turnos confirmados, ordenados por inicio del turno."""
        consulta = (
            select(Recordatorio, Turno.inicio, Paciente.nombre, Profesional.nombre)
            .join(Turno, Turno.id == Recordatorio.turno_id)
            .join(Paciente, Paciente.id == Turno.paciente_id)
            .join(Profesional, Profesional.id == Turno.profesional_id)
            .where(
                Recordatorio.estado.in_(
                    [EstadoRecordatorio.PENDIENTE, EstadoRecordatorio.FALLIDO]
                ),
                Turno.estado == EstadoTurno.CONFIRMADO,
            )
        )
        if profesional_id is not None:
            consulta = consulta.where(Turno.profesional_id == profesional_id)
        consulta = consulta.order_by(Turno.inicio, Recordatorio.id)
        return [tuple(fila) for fila in self._session.execute(consulta).all()]  # type: ignore[misc]

    def obtener_para_marcar(
        self, identificador: uuid.UUID, profesional_id: uuid.UUID | None
    ) -> Recordatorio | None:
        consulta = (
            select(Recordatorio)
            .join(Turno, Turno.id == Recordatorio.turno_id)
            .where(Recordatorio.id == identificador)
        )
        if profesional_id is not None:
            consulta = consulta.where(Turno.profesional_id == profesional_id)
        return self._session.execute(
            consulta.with_for_update(of=Recordatorio)
        ).scalar_one_or_none()

    def detalle(
        self, identificador: uuid.UUID
    ) -> tuple[Recordatorio, datetime, str, str] | None:
        """Fila + datos del turno para serializar el resultado de un marcado."""
        consulta = (
            select(Recordatorio, Turno.inicio, Paciente.nombre, Profesional.nombre)
            .join(Turno, Turno.id == Recordatorio.turno_id)
            .join(Paciente, Paciente.id == Turno.paciente_id)
            .join(Profesional, Profesional.id == Turno.profesional_id)
            .where(Recordatorio.id == identificador)
        )
        fila = self._session.execute(consulta).first()
        return tuple(fila) if fila is not None else None  # type: ignore[return-value]
