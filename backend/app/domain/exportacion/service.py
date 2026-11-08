"""Servicio de exportación: crear/encolar, consultar, descargar y reintentar."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import redis
from rq import Queue

from app.core.errors import DomainError, InfraError
from app.core.settings import get_settings
from app.db.models import EstadoExportacion, Exportacion, TipoExportacion, Usuario
from app.domain.exportacion.schemas import ExportacionCreate
from app.domain.persistence import UnitOfWork

MAX_DIAS = 366
COLA = "default"
JOB_EXPORTAR = "app.workers.jobs.exportar_csv"


def _error(reason: str, mensaje: str, status: int) -> DomainError:
    return DomainError("RN-RP-02", mensaje, status_code=status, details={"reason": reason})


def _no_encontrado() -> DomainError:
    return _error("no_encontrado", "La exportación no existe", 404)


def _validar(tipo: TipoExportacion, desde: datetime | None, hasta: datetime | None) -> None:
    if tipo is TipoExportacion.PACIENTES:
        return
    if (
        desde is not None
        and hasta is not None
        and (hasta <= desde or hasta - desde > timedelta(days=MAX_DIAS))
    ):
        raise _error(
            "rango_invalido",
            "El rango del export no es válido o supera el máximo permitido",
            422,
        )


def encolar(exportacion_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Encola el job en la cola `default`; se puede doblar en tests."""
    conexion = redis.Redis.from_url(get_settings().redis_url)
    Queue(COLA, connection=conexion).enqueue(
        JOB_EXPORTAR, str(exportacion_id), str(tenant_id)
    )


def _encolar_o_fallar(exportacion_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    try:
        encolar(exportacion_id, tenant_id)
    except Exception as exc:
        with UnitOfWork() as uow:
            fila = uow.repository(Exportacion).get(exportacion_id)
            if fila is not None:
                fila.estado = EstadoExportacion.FALLIDO
                fila.error = f"No se pudo encolar: {exc}"[:500]
        raise InfraError(
            "RN-RP-02",
            "No se pudo encolar la exportación; reintentá en unos segundos",
        ) from exc


def crear(
    usuario: Usuario, tipo: TipoExportacion, datos: ExportacionCreate
) -> Exportacion:
    _validar(tipo, datos.desde, datos.hasta)
    with UnitOfWork() as uow:
        fila = uow.repository(Exportacion).add(
            Exportacion(
                tipo=tipo,
                estado=EstadoExportacion.PENDIENTE,
                desde=datos.desde,
                hasta=datos.hasta,
                creado_por=usuario.id,
            )
        )
        uow.session.flush()
        exportacion_id = fila.id
        tenant_id = uow.tenant_id
    _encolar_o_fallar(exportacion_id, tenant_id)
    return obtener(exportacion_id)


def obtener(exportacion_id: uuid.UUID) -> Exportacion:
    with UnitOfWork() as uow:
        fila = uow.repository(Exportacion).get(exportacion_id)
        if fila is None:
            raise _no_encontrado()
        return fila


def descargar(exportacion_id: uuid.UUID) -> tuple[str, str]:
    fila = obtener(exportacion_id)
    if fila.estado is EstadoExportacion.FALLIDO:
        raise _error(
            "fallido",
            f"La exportación falló: {fila.error or 'error desconocido'}",
            409,
        )
    if fila.estado is not EstadoExportacion.LISTO or fila.contenido is None:
        raise _error("no_listo", "La exportación todavía no está lista", 409)
    return fila.contenido, f"{fila.tipo.value}-{fila.id}.csv"


def reintentar(exportacion_id: uuid.UUID) -> Exportacion:
    with UnitOfWork() as uow:
        fila = uow.repository(Exportacion).get(exportacion_id)
        if fila is None:
            raise _no_encontrado()
        if fila.estado is not EstadoExportacion.FALLIDO:
            raise _error(
                "no_reintentable",
                "Solo se puede reintentar una exportación fallida",
                409,
            )
        fila.estado = EstadoExportacion.PENDIENTE
        fila.error = None
        fila.contenido = None
        tenant_id = uow.tenant_id
    _encolar_o_fallar(exportacion_id, tenant_id)
    return obtener(exportacion_id)


__all__ = ["crear", "descargar", "encolar", "obtener", "reintentar"]
