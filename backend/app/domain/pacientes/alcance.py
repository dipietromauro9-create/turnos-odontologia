"""Predicado único del vínculo asistencial, siempre correlacionado por tenant."""

import uuid

from sqlalchemy import ColumnElement, and_, exists, or_, select

from app.db.models import EstadoTurno, Paciente, Profesional, Turno


def condicion_paciente_propio(tenant_id: uuid.UUID, usuario_id: uuid.UUID) -> ColumnElement[bool]:
    vinculo = exists(
        select(Turno.id)
        .join(Profesional, Profesional.id == Turno.profesional_id)
        .where(
            Turno.tenant_id == tenant_id,
            Profesional.tenant_id == tenant_id,
            Profesional.usuario_id == usuario_id,
            Turno.paciente_id == Paciente.id,
            Turno.estado.in_((EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO, EstadoTurno.ATENDIDO)),
        )
        .correlate(Paciente)
    )
    return and_(
        Paciente.tenant_id == tenant_id, or_(Paciente.creado_por_usuario_id == usuario_id, vinculo)
    )
