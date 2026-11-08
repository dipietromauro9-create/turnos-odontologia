"""Job de exportación: metadata RN-RP-02, filas, BOM y estados."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    EstadoExportacion,
    EstadoTurno,
    Exportacion,
    Paciente,
    Tenant,
    TipoExportacion,
    Turno,
)
from app.workers import jobs
from tests.factories import crear_prestacion, crear_profesional, crear_tenant

pytestmark = pytest.mark.integration

DESDE = datetime(2030, 6, 1, tzinfo=UTC)
HASTA = datetime(2030, 6, 30, tzinfo=UTC)


def _contexto(session: Session) -> dict[str, object]:
    tenant = crear_tenant(session, "demo")
    profesional = crear_profesional(session, tenant, nombre="Dra. Ficticia")
    prestacion = crear_prestacion(session, tenant, nombre="Consulta")
    paciente = Paciente(
        tenant_id=tenant.id,
        nombre="Paciente Ficticio",
        telefono="1145550001",
        documento=None,
    )
    session.add(paciente)
    session.commit()
    return dict(
        tenant=tenant,
        profesional=profesional,
        prestacion=prestacion,
        paciente=paciente,
    )


def _turno(
    session: Session,
    contexto: dict[str, object],
    *,
    inicio: datetime,
    codigo: str,
    estado: EstadoTurno = EstadoTurno.CONFIRMADO,
) -> Turno:
    turno = Turno(
        tenant_id=contexto["tenant"].id,  # type: ignore[union-attr]
        profesional_id=contexto["profesional"].id,  # type: ignore[union-attr]
        paciente_id=contexto["paciente"].id,  # type: ignore[union-attr]
        prestacion_id=contexto["prestacion"].id,  # type: ignore[union-attr]
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado=estado,
        codigo_publico=codigo,
        es_sobreturno=False,
    )
    session.add(turno)
    session.commit()
    return turno


def _exportacion(
    session: Session,
    tenant: Tenant,
    tipo: TipoExportacion,
    *,
    desde: datetime | None = DESDE,
    hasta: datetime | None = HASTA,
) -> Exportacion:
    fila = Exportacion(
        tenant_id=tenant.id,
        tipo=tipo,
        estado=EstadoExportacion.PENDIENTE,
        desde=desde,
        hasta=hasta,
    )
    session.add(fila)
    session.commit()
    return fila


def _filas_csv(contenido: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(contenido.lstrip("\ufeff"))))


def test_export_de_turnos_incluye_metadata_encabezados_y_filas(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        contexto = _contexto(session)
        _turno(
            session, contexto, inicio=datetime(2030, 6, 3, 12, tzinfo=UTC), codigo="abcdefgh1234"
        )
        _turno(
            session,
            contexto,
            inicio=datetime(2030, 6, 4, 12, tzinfo=UTC),
            codigo="zyxwvuts5678",
            estado=EstadoTurno.ATENDIDO,
        )
        _turno(
            session, contexto, inicio=datetime(2030, 7, 1, 12, tzinfo=UTC), codigo="1234abcdefgh"
        )
        fila = _exportacion(session, contexto["tenant"], TipoExportacion.TURNOS)  # type: ignore[arg-type]

    resultado = jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    assert resultado["estado"] == "listo"
    with session_factory() as session:
        actualizada = session.get(Exportacion, fila.id)
        assert actualizada is not None and actualizada.estado is EstadoExportacion.LISTO
        contenido = actualizada.contenido or ""
    assert contenido.startswith("\ufeff")
    lineas = _filas_csv(contenido)
    assert lineas[0][0].startswith("# tenant_id=")
    assert "generado_en=" in lineas[0][0]
    assert lineas[1] == [
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
    assert len(lineas) == 4  # metadata + encabezado + 2 turnos en rango
    assert "Dra. Ficticia" in lineas[2][4]


def test_export_de_pacientes_incluye_nulos(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        contexto = _contexto(session)
        fila = _exportacion(session, contexto["tenant"], TipoExportacion.PACIENTES)  # type: ignore[arg-type]

    jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    with session_factory() as session:
        contenido = session.get(Exportacion, fila.id).contenido or ""  # type: ignore[union-attr]
    lineas = _filas_csv(contenido)
    assert lineas[1] == ["id", "nombre", "telefono", "documento", "fecha_nac", "creado_en"]
    assert lineas[2][3] == "" and lineas[2][4] == ""


def test_rango_vacio_solo_deja_metadata_y_encabezado(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        contexto = _contexto(session)
        _turno(
            session, contexto, inicio=datetime(2030, 7, 1, 12, tzinfo=UTC), codigo="abcdefgh1234"
        )
        fila = _exportacion(
            session,
            contexto["tenant"],  # type: ignore[arg-type]
            TipoExportacion.TURNOS,
            desde=datetime(2030, 6, 1, tzinfo=UTC),
            hasta=datetime(2030, 6, 2, tzinfo=UTC),
        )

    jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    with session_factory() as session:
        contenido = session.get(Exportacion, fila.id).contenido or ""  # type: ignore[union-attr]
    assert len(_filas_csv(contenido)) == 2


def test_solo_exporta_el_tenant_de_la_fila(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        propio = _contexto(session)
        _turno(session, propio, inicio=datetime(2030, 6, 3, 12, tzinfo=UTC), codigo="abcdefgh1234")
        otro = crear_tenant(session, "otro")
        otro_profesional = crear_profesional(session, otro, nombre="Dra. Ajena")
        otra_prestacion = crear_prestacion(session, otro)
        otro_paciente = Paciente(tenant_id=otro.id, nombre="Paciente Ajeno", telefono="1145559999")
        session.add(otro_paciente)
        session.commit()
        _turno(
            session,
            {
                "tenant": otro,
                "profesional": otro_profesional,
                "prestacion": otra_prestacion,
                "paciente": otro_paciente,
            },
            inicio=datetime(2030, 6, 3, 13, tzinfo=UTC),
            codigo="zyxwvuts5678",
        )
        fila = _exportacion(session, propio["tenant"], TipoExportacion.TURNOS)  # type: ignore[arg-type]

    jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    with session_factory() as session:
        contenido = session.get(Exportacion, fila.id).contenido or ""  # type: ignore[union-attr]
    assert "Paciente Ficticio" in contenido and "Paciente Ajeno" not in contenido


def test_nombres_con_comas_y_comillas_se_escapan(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        contexto = _contexto(session)
        paciente = contexto["paciente"]
        paciente.nombre = 'Pérez, "Ana"'  # type: ignore[union-attr]
        session.commit()
        fila = _exportacion(session, contexto["tenant"], TipoExportacion.PACIENTES)  # type: ignore[arg-type]

    jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    with session_factory() as session:
        contenido = session.get(Exportacion, fila.id).contenido or ""  # type: ignore[union-attr]
    lineas = _filas_csv(contenido)
    assert lineas[2][1] == 'Pérez, "Ana"'


def test_un_error_del_job_deja_fallido_con_mensaje(
    app_env: None, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.exportacion import generador

    with session_factory() as session:
        contexto = _contexto(session)
        fila = _exportacion(session, contexto["tenant"], TipoExportacion.TURNOS)  # type: ignore[arg-type]

    def _falla(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("falla ficticia del job")

    monkeypatch.setattr(generador, "_contenido_csv", _falla)

    resultado = jobs.exportar_csv(str(fila.id), str(fila.tenant_id))

    assert resultado["estado"] == "fallido"
    with session_factory() as session:
        actualizada = session.get(Exportacion, fila.id)
        assert actualizada is not None and actualizada.estado is EstadoExportacion.FALLIDO
        assert "falla ficticia" in (actualizada.error or "")


def test_reejecutar_sobre_listo_no_reescribe(
    app_env: None, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        contexto = _contexto(session)
        fila = _exportacion(session, contexto["tenant"], TipoExportacion.TURNOS)  # type: ignore[arg-type]

    jobs.exportar_csv(str(fila.id), str(fila.tenant_id))
    with session_factory() as session:
        primero = session.get(Exportacion, fila.id).contenido  # type: ignore[union-attr]

    resultado = jobs.exportar_csv(str(fila.id), str(fila.tenant_id))
    with session_factory() as session:
        segundo = session.get(Exportacion, fila.id).contenido  # type: ignore[union-attr]

    assert resultado["estado"] == "listo"
    assert primero == segundo
