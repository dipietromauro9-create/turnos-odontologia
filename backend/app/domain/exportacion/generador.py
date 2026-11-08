"""Generación del CSV de una exportación (RN-RP-02).

El job corre fuera de una request: recibe `tenant_id` explícito, abre una
`tenant_session` y deja el archivo en `contenido`. No crea ni modifica turnos.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import EstadoExportacion, Exportacion, TipoExportacion
from app.db.session import TenantSession, tenant_session
from app.domain.exportacion import consultas

ENCABEZADOS_TURNOS = [
    "id",
    "inicio",
    "fin",
    "estado",
    "profesional",
    "prestacion",
    "paciente",
    "telefono",
    "es_sobreturno",
    "codigo_publico",
    "creado_en",
]
ENCABEZADOS_PACIENTES = ["id", "nombre", "telefono", "documento", "fecha_nac", "creado_en"]


def _metadata(fila: Exportacion) -> str:
    desde = fila.desde.isoformat() if fila.desde is not None else ""
    hasta = fila.hasta.isoformat() if fila.hasta is not None else ""
    return (
        f"# tenant_id={fila.tenant_id}; generado_en={datetime.now(UTC).isoformat()}; "
        f"tipo={fila.tipo.value}; desde={desde}; hasta={hasta}"
    )


def _contenido_csv(session: TenantSession, fila: Exportacion) -> str:
    salida = io.StringIO(newline="")
    writer = csv.writer(salida)
    writer.writerow([_metadata(fila)])
    if fila.tipo is TipoExportacion.TURNOS:
        writer.writerow(ENCABEZADOS_TURNOS)
        for turno, profesional, prestacion, paciente, telefono in consultas.turnos(
            session, fila.desde, fila.hasta
        ):
            writer.writerow(
                [
                    str(turno.id),
                    turno.inicio.isoformat(),
                    turno.fin.isoformat(),
                    turno.estado.value,
                    profesional,
                    prestacion,
                    paciente,
                    telefono,
                    turno.es_sobreturno,
                    turno.codigo_publico,
                    turno.creado_en.isoformat(),
                ]
            )
    else:
        writer.writerow(ENCABEZADOS_PACIENTES)
        for paciente in consultas.pacientes(session):
            writer.writerow(
                [
                    str(paciente.id),
                    paciente.nombre,
                    paciente.telefono,
                    paciente.documento or "",
                    paciente.fecha_nac.isoformat() if paciente.fecha_nac is not None else "",
                    paciente.creado_en.isoformat(),
                ]
            )
    return "\ufeff" + salida.getvalue()


def generar(exportacion_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    """Genera el CSV y deja la fila en `listo` o `fallido` (idempotente)."""
    with tenant_session(tenant_id) as session:
        fila = session.execute(
            select(Exportacion).where(Exportacion.id == exportacion_id)
        ).scalar_one_or_none()
        if fila is None:
            return {"estado": "no_encontrada"}
        if fila.estado is EstadoExportacion.LISTO:
            return {"estado": "listo"}
        fila.estado = EstadoExportacion.PROCESANDO
        session.commit()
        try:
            fila.contenido = _contenido_csv(session, fila)
            fila.estado = EstadoExportacion.LISTO
            fila.error = None
        except Exception as exc:  # noqa: BLE001 - el job registra el fallo y sigue
            session.rollback()
            fila = session.execute(
                select(Exportacion).where(Exportacion.id == exportacion_id)
            ).scalar_one()
            fila.estado = EstadoExportacion.FALLIDO
            fila.error = str(exc)[:500]
        session.commit()
        return {"estado": fila.estado.value}


__all__ = ["generar"]
