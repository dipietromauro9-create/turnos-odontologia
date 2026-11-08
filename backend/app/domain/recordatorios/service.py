"""Generación idempotente y multi-tenant de recordatorios (RN-CO-01, R3).

El job corre fuera de una request: lista tenants con la sesión de sistema
(acotada a la tabla `tenant`) y genera con una `tenant_session` por tenant, con
commit independiente para que el fallo de uno no revierta a los demás.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.core.settings import Settings, get_settings
from app.db.models import (
    CanalRecordatorio,
    EstadoRecordatorio,
    Recordatorio,
    Tenant,
    Usuario,
)
from app.db.session import system_session, tenant_session
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.persistence import UnitOfWork
from app.domain.recordatorios.plantilla import parse_ventana, texto_recordatorio
from app.domain.recordatorios.repository import RecordatoriosRepository

logger = logging.getLogger("turnos.recordatorios")


def generar(ahora: datetime | None = None) -> dict[str, int]:
    """Crea un recordatorio pendiente por turno confirmado próximo sin aviso."""
    settings = get_settings()
    minimo, maximo = parse_ventana(settings.recordatorio_ventana_hs)
    tz = ZoneInfo(settings.tz)
    momento = (ahora or datetime.now(UTC)).astimezone(UTC)
    desde = momento + timedelta(hours=minimo)
    hasta = momento + timedelta(hours=maximo)
    antiguedad_maxima = momento - timedelta(hours=minimo)

    with system_session() as session:
        tenants: list[uuid.UUID] = list(session.execute(select(Tenant.id)).scalars())

    creados = 0
    for tenant_id in tenants:
        try:
            creados += _generar_tenant(
                tenant_id,
                ahora=momento,
                desde=desde,
                hasta=hasta,
                antiguedad_maxima=antiguedad_maxima,
                tz=tz,
                direccion=settings.consultorio_direccion,
            )
        except Exception:
            logger.exception("Fallo generando recordatorios para el tenant %s", tenant_id)
            continue

    return {"tenants": len(tenants), "creados": creados}


def _generar_tenant(
    tenant_id: uuid.UUID,
    *,
    ahora: datetime,
    desde: datetime,
    hasta: datetime,
    antiguedad_maxima: datetime,
    tz: ZoneInfo,
    direccion: str,
) -> int:
    creados = 0
    with tenant_session(tenant_id) as session:
        repositorio = RecordatoriosRepository(session)
        candidatos = repositorio.candidatos(
            ahora=ahora,
            desde=desde,
            hasta=hasta,
            antiguedad_maxima=antiguedad_maxima,
        )
        for candidato in candidatos:
            texto = texto_recordatorio(
                paciente=candidato.paciente,
                profesional=candidato.profesional,
                inicio=candidato.inicio,
                tz=tz,
                direccion=direccion,
            )
            try:
                with session.begin_nested():
                    repositorio.add(
                        Recordatorio(
                            turno_id=candidato.turno_id,
                            canal=CanalRecordatorio.WHATSAPP_MANUAL,
                            texto=texto,
                            estado=EstadoRecordatorio.PENDIENTE,
                        )
                    )
            except IntegrityError:
                continue
            creados += 1
        session.commit()
    return creados


@dataclass(frozen=True)
class EnCola:
    """Vista de un recordatorio lista para serializar (texto vigente del turno)."""

    id: uuid.UUID
    turno_id: uuid.UUID
    canal: CanalRecordatorio
    estado: EstadoRecordatorio
    texto: str
    inicio: datetime
    paciente: str
    profesional: str
    enviado_por: uuid.UUID | None
    creado_en: datetime


def _a_cola(
    fila: Recordatorio,
    inicio: datetime,
    paciente: str,
    profesional: str,
    settings: Settings,
) -> EnCola:
    return EnCola(
        id=fila.id,
        turno_id=fila.turno_id,
        canal=fila.canal,
        estado=fila.estado,
        texto=texto_recordatorio(
            paciente=paciente,
            profesional=profesional,
            inicio=inicio,
            tz=ZoneInfo(settings.tz),
            direccion=settings.consultorio_direccion,
        ),
        inicio=inicio,
        paciente=paciente,
        profesional=profesional,
        enviado_por=fila.enviado_por,
        creado_en=fila.creado_en,
    )


def listar(usuario: Usuario) -> list[EnCola]:
    """Cola de recepción: pendientes y fallidos de turnos confirmados, por alcance."""
    settings = get_settings()
    with UnitOfWork() as uow:
        profesional_id = profesional_del_alcance(uow.session, usuario, None)
        filas = RecordatoriosRepository(uow.session).en_cola(profesional_id)
        return [_a_cola(*fila, settings) for fila in filas]


def marcar_enviado(identificador: uuid.UUID, usuario: Usuario) -> EnCola:
    return _marcar(identificador, usuario, EstadoRecordatorio.ENVIADO)


def marcar_fallido(identificador: uuid.UUID, usuario: Usuario) -> EnCola:
    return _marcar(identificador, usuario, EstadoRecordatorio.FALLIDO)


def _marcar(
    identificador: uuid.UUID, usuario: Usuario, destino: EstadoRecordatorio
) -> EnCola:
    settings = get_settings()
    with UnitOfWork() as uow:
        repositorio = RecordatoriosRepository(uow.session)
        profesional_id = profesional_del_alcance(uow.session, usuario, None)
        fila = repositorio.obtener_para_marcar(identificador, profesional_id)
        if fila is None:
            raise DomainError(
                "RN-CO-03",
                "El recordatorio no existe",
                status_code=404,
                details={"reason": "no_encontrado"},
            )
        if fila.estado is EstadoRecordatorio.ENVIADO:
            raise DomainError(
                "RN-CO-03",
                "El recordatorio ya fue enviado",
                status_code=409,
                details={"reason": "ya_enviado"},
            )
        fila.estado = destino
        if destino is EstadoRecordatorio.ENVIADO:
            fila.enviado_por = usuario.id
        uow.session.flush()
        detalle = repositorio.detalle(identificador)
        assert detalle is not None
        return _a_cola(*detalle, settings)
