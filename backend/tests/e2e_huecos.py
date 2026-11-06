"""C-08 E2E HTTP contra una base aislada recién migrada 0001→0006.

No se colecta con pytest. Crea una base exclusiva, siembra de forma idempotente,
levanta la API real y recorre login, huecos, bloqueos, cancelación, RBAC y
frontera de tenant. Al terminar elimina la base creada y limpia Redis de pruebas.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as hora
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import redis as redis_lib
from sqlalchemy import create_engine, make_url, select, text

from app.core.settings import get_settings
from app.db.models import Disponibilidad, Paciente, Prestacion, RolUsuario, Tenant, Turno
from app.db.seed import DEMO_PASSWORDS, run_seed
from app.db.session import reset_tenant_cache, system_session, tenant_session
from app.domain.huecos.calculo import RANGO_MAXIMO_DIAS
from tests.conftest import _ensure_database, _run_migrations
from tests.factories import (
    crear_prestacion,
    crear_profesional,
    crear_tenant,
    crear_usuario_con_password,
)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
LUNES = date(2030, 6, 3)
CLAVE_PROFESIONAL = "clave-e2e-ficticia-2026"
CLAVES_HUECO = {"inicio", "fin", "profesional_id", "prestacion_id"}


def respuesta(res: httpx.Response, status: int, code: str | None = None) -> dict:
    contenido = res.json() if res.content else {}
    assert res.status_code == status, {"status": res.status_code, "code": contenido.get("code")}
    if code is not None:
        assert contenido.get("code") == code
    return contenido


def _drop_database(url) -> None:
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    finally:
        engine.dispose()


def _limpiar_redis(redis_url: str) -> None:
    client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    try:
        claves = list(client.scan_iter("auth:*"))
        if claves:
            client.delete(*claves)
    finally:
        client.close()


def main() -> None:
    base = make_url(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://turnos:turnos_dev@localhost:5432/turnos",
        )
    )
    url = base.set(database=f"turnos_c08_e2e_{uuid.uuid4().hex[:10]}")
    redis_url = "redis://localhost:6379/2"
    os.environ.update(
        DATABASE_URL=url.render_as_string(hide_password=False),
        REDIS_URL=redis_url,
        SECRET_KEY="c08-e2e-ficticio-" + "t" * 40,
        ACCESS_MINUTES="15",
        REFRESH_DAYS="7",
        TENANT_DEFAULT_SLUG="demo",
        FRONTEND_ORIGIN="http://127.0.0.1:15174",
        RECORDATORIO_VENTANA_HS="24,48",
        TZ="America/Argentina/Buenos_Aires",
    )
    get_settings.cache_clear()
    _limpiar_redis(redis_url)
    _ensure_database(url)
    _run_migrations(url)

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "0006_turno", version
    finally:
        engine.dispose()

    primero = run_seed()
    segundo = run_seed()
    assert primero["tenant_creado"] is True
    assert primero["turnos_creados"] == 3
    assert segundo == {**segundo, "tenant_creado": False, "turnos_creados": 0}

    with system_session() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
        otro_tenant = crear_tenant(session, "otro-e2e", "Otro Consultorio Ficticio")

    with tenant_session(tenant.id) as session:
        usuario = crear_usuario_con_password(
            session,
            tenant,
            "profesional-e2e@demo",
            CLAVE_PROFESIONAL,
            RolUsuario.PROFESIONAL,
        )
        profesional = crear_profesional(
            session, tenant, usuario=usuario, nombre="Profesional E2E Ficticio"
        )
        segundo_profesional = crear_profesional(session, tenant, nombre="Segundo E2E Ficticio")
        prestacion = session.execute(
            select(Prestacion)
            .where(Prestacion.tenant_id == tenant.id, Prestacion.nombre == "Consulta")
            .order_by(Prestacion.activa.desc(), Prestacion.creado_en, Prestacion.id)
            .limit(1)
        ).scalar_one()
        pacientes = list(
            session.execute(select(Paciente).where(Paciente.tenant_id == tenant.id)).scalars()
        )
        assert pacientes
        session.add(
            Disponibilidad(
                tenant_id=tenant.id,
                profesional_id=profesional.id,
                dia_semana=0,
                hora_desde=hora(9),
                hora_hasta=hora(12),
            )
        )
        session.commit()

    with tenant_session(otro_tenant.id) as session:
        ajeno = crear_profesional(session, otro_tenant, nombre="Ajeno E2E Ficticio")
        prestacion_ajena = crear_prestacion(session, otro_tenant, nombre="Ajena E2E Ficticia")

    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
    base_http = f"http://127.0.0.1:{puerto}"
    with Path("/tmp/c08-e2e-api.log").open("w", encoding="utf-8") as log:
        servidor = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(puerto),
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url=base_http, timeout=20) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert servidor.poll() is None, "La API E2E terminó antes de iniciar"
                    time.sleep(0.1)
                else:
                    raise AssertionError("La API E2E no inició")

                def acceso(email: str, password: str) -> dict[str, str]:
                    token = respuesta(
                        client.post("/auth/login", json={"email": email, "password": password}),
                        200,
                    )
                    cabecera = {"Authorization": f"Bearer {token['access_token']}"}
                    me = respuesta(client.get("/auth/me", headers=cabecera), 200)
                    assert me["email"] == email
                    return cabecera

                dueno = acceso("dueno@demo", DEMO_PASSWORDS["dueno@demo"])
                recepcion = acceso("recepcion@demo", DEMO_PASSWORDS["recepcion@demo"])
                propio = acceso(usuario.email, CLAVE_PROFESIONAL)

                desde = datetime.combine(LUNES, hora(0), TZ)
                hasta = desde + timedelta(days=7)
                parametros = {
                    "profesional_id": str(profesional.id),
                    "prestacion_id": str(prestacion.id),
                    "desde": desde.isoformat(),
                    "hasta": hasta.isoformat(),
                }
                respuesta(client.get("/disponibilidad/huecos", params=parametros), 401, "RN-AU-01")

                semana = respuesta(
                    client.get("/disponibilidad/huecos", params=parametros, headers=recepcion), 200
                )
                assert semana and all(set(hueco) == CLAVES_HUECO for hueco in semana)
                assert [h["inicio"] for h in semana] == sorted(h["inicio"] for h in semana)
                assert all(h["profesional_id"] == str(profesional.id) for h in semana)
                assert "Paciente Demo" not in json.dumps(semana)
                assert "1145550001" not in json.dumps(semana)

                propia_semana = respuesta(
                    client.get("/disponibilidad/huecos", params=parametros, headers=propio), 200
                )
                assert propia_semana == semana
                respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "profesional_id": str(segundo_profesional.id)},
                        headers=propio,
                    ),
                    403,
                    "RN-AU-03",
                )
                respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "profesional_id": str(ajeno.id)},
                        headers=recepcion,
                    ),
                    404,
                    "RN-AG-01",
                )
                respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "prestacion_id": str(prestacion_ajena.id)},
                        headers=recepcion,
                    ),
                    404,
                    "RN-AG-01",
                )
                hasta_invalida = (desde + timedelta(days=RANGO_MAXIMO_DIAS, seconds=1)).isoformat()
                respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={
                            **parametros,
                            "hasta": hasta_invalida,
                        },
                        headers=recepcion,
                    ),
                    422,
                )

                plantilla = respuesta(
                    client.get(
                        f"/disponibilidad?profesional_id={profesional.id}", headers=recepcion
                    ),
                    200,
                )
                assert len(plantilla) == 1
                assert (plantilla[0]["dia_semana"], plantilla[0]["hora_desde"]) == (0, "09:00:00")

                bloqueo = respuesta(
                    client.post(
                        "/bloqueos",
                        headers=dueno,
                        json={
                            "profesional_id": str(profesional.id),
                            "desde": datetime.combine(LUNES, hora(9), TZ).isoformat(),
                            "hasta": datetime.combine(LUNES, hora(9, 30), TZ).isoformat(),
                            "motivo": "Cierre ficticio E2E",
                        },
                    ),
                    201,
                )
                tras_bloqueo = respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "hasta": (desde + timedelta(days=1)).isoformat()},
                        headers=recepcion,
                    ),
                    200,
                )
                assert "2030-06-03T09:00:00-03:00" not in {h["inicio"] for h in tras_bloqueo}
                assert "2030-06-03T09:30:00-03:00" in {h["inicio"] for h in tras_bloqueo}
                assert bloqueo["profesional_id"] == str(profesional.id)

                turno = respuesta(
                    client.post(
                        "/turnos",
                        headers=recepcion,
                        json={
                            "profesional_id": str(profesional.id),
                            "prestacion_id": str(prestacion.id),
                            "paciente_id": str(pacientes[0].id),
                            "inicio": datetime.combine(LUNES, hora(10), TZ).isoformat(),
                        },
                    ),
                    201,
                )
                con_turno = respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "hasta": (desde + timedelta(days=1)).isoformat()},
                        headers=recepcion,
                    ),
                    200,
                )
                assert "2030-06-03T10:00:00-03:00" not in {h["inicio"] for h in con_turno}
                respuesta(client.post(f"/turnos/{turno['id']}/cancelar", headers=recepcion), 200)
                liberado = respuesta(
                    client.get(
                        "/disponibilidad/huecos",
                        params={**parametros, "hasta": (desde + timedelta(days=1)).isoformat()},
                        headers=recepcion,
                    ),
                    200,
                )
                assert "2030-06-03T10:00:00-03:00" in {h["inicio"] for h in liberado}

            with tenant_session(tenant.id) as session:
                assert session.execute(select(Turno)).scalars().all()
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)

    reset_tenant_cache()
    _drop_database(url)
    _limpiar_redis(redis_url)
    print(
        json.dumps(
            {
                "database": url.database,
                "migracion": version,
                "seed": "idempotente",
                "huecos_semana": len(semana),
                "bloqueo_oculta_hueco": True,
                "cancelacion_libera_hueco": True,
                "rbac_403": True,
                "tenant_404": True,
                "plantilla_intacta": True,
                "result": "PASS",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
