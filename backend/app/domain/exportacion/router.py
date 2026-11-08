"""Rutas de exportación: exclusivas del dueño (RN-AU-02)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response

from app.db.models import EstadoExportacion, Exportacion, TipoExportacion
from app.domain.auth.dependencies import CurrentUserDep, require_dueno
from app.domain.exportacion import service
from app.domain.exportacion.schemas import ExportacionCreate, ExportacionPublic

router = APIRouter(
    prefix="/export",
    tags=["export"],
    dependencies=[Depends(require_dueno)],
)


def _salida(fila: Exportacion) -> ExportacionPublic:
    listo = fila.estado is EstadoExportacion.LISTO
    return ExportacionPublic(
        id=fila.id,
        tipo=fila.tipo,
        estado=fila.estado,
        desde=fila.desde,
        hasta=fila.hasta,
        error=fila.error,
        creado_en=fila.creado_en,
        descarga_url=f"/export/{fila.id}/archivo" if listo else None,
    )


@router.post("/turnos.csv", status_code=202)
def exportar_turnos(
    datos: ExportacionCreate, usuario: CurrentUserDep
) -> ExportacionPublic:
    return _salida(service.crear(usuario, TipoExportacion.TURNOS, datos))


@router.post("/pacientes.csv", status_code=202)
def exportar_pacientes(
    datos: ExportacionCreate, usuario: CurrentUserDep
) -> ExportacionPublic:
    return _salida(service.crear(usuario, TipoExportacion.PACIENTES, datos))


@router.get("/{identificador}")
def estado_export(identificador: uuid.UUID) -> ExportacionPublic:
    return _salida(service.obtener(identificador))


@router.get("/{identificador}/archivo")
def descargar_export(identificador: uuid.UUID) -> Response:
    contenido, nombre = service.descargar(identificador)
    return Response(
        content=contenido,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("/{identificador}/reintentar", status_code=202)
def reintentar_export(identificador: uuid.UUID) -> ExportacionPublic:
    return _salida(service.reintentar(identificador))
