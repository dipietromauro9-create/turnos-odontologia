"""C-07 HTTP real en DB nueva exclusiva; ejecutar dentro del runtime de pruebas.

No se colecta con pytest. Usa c06-postgres y Redis DB 1, nunca la demo manual.
Las aserciones fallan con status/código, sin imprimir tokens ni credenciales.
"""

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from datetime import time as hora
from pathlib import Path
from threading import Barrier
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import make_url, select

from app.core.settings import get_settings
from app.db.models import Disponibilidad, Paciente, RolUsuario, Tenant, Turno
from app.db.seed import DEMO_PASSWORDS, run_seed
from app.db.session import system_session, tenant_session
from tests.conftest import _ensure_database, _run_migrations
from tests.factories import crear_profesional, crear_usuario_con_password


def respuesta(res: httpx.Response, status: int, code: str | None = None) -> dict:
    contenido = res.json() if res.content else {}
    assert res.status_code == status, {"status": res.status_code, "code": contenido.get("code")}
    if code is not None:
        assert contenido.get("code") == code
    return contenido


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    assert url.host == "c06-postgres", "Solo se permite el PostgreSQL exclusivo de pruebas"
    url = url.set(database=f"c07_e2e_{uuid.uuid4().hex[:10]}")
    os.environ.update(
        DATABASE_URL=url.render_as_string(hide_password=False),
        REDIS_URL="redis://c06-redis:6379/1",
        SECRET_KEY="c07-ficticio-" + "t" * 40,
        ACCESS_MINUTES="15",
        REFRESH_DAYS="7",
        TENANT_DEFAULT_SLUG="demo",
        FRONTEND_ORIGIN="http://127.0.0.1:15173",
        RECORDATORIO_VENTANA_HS="24,48",
        TZ="America/Argentina/Buenos_Aires",
    )
    get_settings.cache_clear()
    _ensure_database(url)
    _run_migrations(url)
    assert run_seed()["turnos_creados"] == 3
    assert run_seed()["turnos_creados"] == 0
    with system_session() as session:
        tenant = session.execute(select(Tenant).where(Tenant.slug == "demo")).scalar_one()
    clave_profesional = "clave-e2e-ficticia-2026"
    with tenant_session(tenant.id) as session:
        pro = crear_usuario_con_password(
            session, tenant, "profesional-e2e@demo", clave_profesional, RolUsuario.PROFESIONAL
        )
        profesional = crear_profesional(session, tenant, usuario=pro)
        session.add(
            Disponibilidad(
                tenant_id=tenant.id,
                profesional_id=profesional.id,
                dia_semana=0,
                hora_desde=hora(9),
                hora_hasta=hora(13),
            )
        )
        pacientes = list(
            session.execute(
                select(Paciente).where(Paciente.tenant_id == tenant.id).order_by(Paciente.telefono)
            ).scalars()
        )
        ejemplo = (
            session.execute(select(Turno).where(Turno.tenant_id == tenant.id)).scalars().first()
        )
        prestacion_id = ejemplo.prestacion_id
        session.commit()
    inicio = datetime(2030, 6, 3, 9, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))

    def payload(fecha: datetime, paciente=0, **extras: object) -> dict:
        return dict(
            profesional_id=str(profesional.id),
            prestacion_id=str(prestacion_id),
            paciente_id=str(pacientes[paciente].id),
            inicio=fecha.isoformat(),
            **extras,
        )

    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
    base = f"http://127.0.0.1:{puerto}"
    with Path("/tmp/c07-e2e-api.log").open("w", encoding="utf-8") as log:
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
            with httpx.Client(base_url=base, timeout=20) as client:
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
                        client.post("/auth/login", json={"email": email, "password": password}), 200
                    )
                    cabecera = {"Authorization": f"Bearer {token['access_token']}"}
                    assert (
                        respuesta(client.get("/auth/me", headers=cabecera), 200)["email"] == email
                    )
                    return cabecera

                dueno = acceso("dueno@demo", DEMO_PASSWORDS["dueno@demo"])
                recepcion = acceso("recepcion@demo", DEMO_PASSWORDS["recepcion@demo"])
                propio = acceso(pro.email, clave_profesional)
                respuesta(client.get("/turnos"), 401, "RN-AU-01")
                respuesta(
                    client.get(f"/pacientes/{pacientes[0].id}", headers=propio), 403, "RN-AU-03"
                )
                primero = respuesta(
                    client.post("/turnos", json=payload(inicio), headers=recepcion), 201
                )
                assert datetime.fromisoformat(primero["fin"]) - datetime.fromisoformat(
                    primero["inicio"]
                ) == timedelta(minutes=30)
                respuesta(client.get(f"/pacientes/{pacientes[0].id}", headers=propio), 200)
                confirmado = respuesta(
                    client.patch(
                        f"/turnos/{primero['id']}", json={"estado": "confirmado"}, headers=propio
                    ),
                    200,
                )
                respuesta(
                    client.post(f"/turnos/{primero['id']}/confirmar", headers=propio),
                    422,
                    "RN-TU-04",
                )
                segundo = respuesta(
                    client.post(
                        "/turnos", json=payload(inicio + timedelta(hours=1)), headers=recepcion
                    ),
                    201,
                )
                respuesta(
                    client.post(
                        f"/turnos/{primero['id']}/reprogramar",
                        headers=propio,
                        json={"nuevo_inicio": segundo["inicio"]},
                    ),
                    409,
                    "RN-TU-01",
                )
                assert (
                    respuesta(client.get(f"/turnos/{primero['id']}", headers=propio), 200)
                    == confirmado
                )
                movido = respuesta(
                    client.post(
                        f"/turnos/{primero['id']}/reprogramar",
                        headers=propio,
                        json={"nuevo_inicio": (inicio + timedelta(minutes=15)).isoformat()},
                    ),
                    200,
                )
                assert (movido["id"], movido["codigo_publico"], movido["estado"]) == (
                    primero["id"],
                    primero["codigo_publico"],
                    "confirmado",
                )
                for fila in (primero, segundo):
                    respuesta(client.post(f"/turnos/{fila['id']}/cancelar", headers=propio), 200)
                respuesta(
                    client.get(f"/pacientes/{pacientes[0].id}", headers=propio), 403, "RN-AU-03"
                )
                urgencia = respuesta(
                    client.post(
                        "/turnos",
                        headers=recepcion,
                        json=payload(
                            inicio.replace(hour=18),
                            1,
                            es_sobreturno=True,
                            motivo_sobreturno="Dolor ficticio",
                        ),
                    ),
                    201,
                )
                assert urgencia["estado"] == "confirmado"
                respuesta(
                    client.post(
                        "/bloqueos",
                        headers=dueno,
                        json={
                            "profesional_id": None,
                            "desde": inicio.replace(hour=19).isoformat(),
                            "hasta": inicio.replace(hour=20).isoformat(),
                            "motivo": "Cierre ficticio",
                        },
                    ),
                    201,
                )
                respuesta(
                    client.post(
                        "/turnos",
                        headers=recepcion,
                        json=payload(
                            inicio.replace(hour=19),
                            1,
                            es_sobreturno=True,
                            motivo_sobreturno="Dolor ficticio",
                        ),
                    ),
                    409,
                    "RN-AG-02",
                )
                barrera = Barrier(2)

                def competir(_indice):
                    with httpx.Client(base_url=base, timeout=20) as otro_client:
                        barrera.wait(timeout=10)
                        res = otro_client.post(
                            "/turnos", headers=recepcion, json=payload(inicio.replace(hour=11), 1)
                        )
                        return res.status_code, res.json()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    carrera = list(pool.map(competir, [0, 1]))
                assert sorted(status for status, _ in carrera) == [201, 409]
                assert (
                    next(cuerpo for status, cuerpo in carrera if status == 409)["code"]
                    == "RN-TU-01"
                )
                respuesta(client.post(f"/turnos/{urgencia['id']}/atender", headers=propio), 200)
                respuesta(
                    client.post(f"/turnos/{urgencia['id']}/cancelar", headers=propio),
                    422,
                    "RN-TU-04",
                )
                listado = client.get("/turnos", headers=propio).json()
                assert len(listado) == 4 and all(
                    r["profesional_id"] == str(profesional.id) for r in listado
                )
            with tenant_session(tenant.id) as session:
                filas = list(
                    session.execute(select(Turno).where(Turno.tenant_id == tenant.id)).scalars()
                )
                assert len(filas) == 7
                assert (
                    sum(
                        f.profesional_id == profesional.id and f.inicio == inicio.replace(hour=11)
                        for f in filas
                    )
                    == 1
                )
            print(
                json.dumps(
                    {
                        "database": url.database,
                        "roles": 3,
                        "http_race": [201, 409],
                        "seed": "idempotente",
                        "rollback": "intacto",
                        "ficha_revocada": True,
                        "result": "PASS",
                    }
                ),
                flush=True,
            )
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)


if __name__ == "__main__":
    main()
