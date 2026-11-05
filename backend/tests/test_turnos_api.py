"""API interna real de turnos, roles, contrato de edición y frontera pública."""

from datetime import datetime, timedelta

import pytest

from app.db.models import EstadoTurno, RolUsuario, Turno
from app.db.session import tenant_context
from app.domain.turnos.schemas import TurnoCreate
from app.domain.turnos.service import crear
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_usuario
from tests.test_agenda_api import cabecera
from tests.test_pacientes_turnos_scope import asignar
from tests.test_pacientes_turnos_scope import entorno as entorno
from tests.turnos_factories import AHORA, INICIO, entorno_turnos

pytestmark = pytest.mark.integration


@pytest.fixture()
def client(entorno):
    return cliente(app_de_prueba()[0])


@pytest.fixture()
def recepcion(entorno, session_factory):
    with session_factory() as session:
        return crear_usuario(session, entorno.base.tenant, "recepcion@demo", RolUsuario.RECEPCION)


def payload(entorno, **cambios):
    datos = dict(
        profesional_id=str(entorno.profesional.id),
        paciente_id=str(entorno.base.paciente.id),
        prestacion_id=str(entorno.base.prestacion.id),
        inicio=INICIO.isoformat(),
    )
    datos.update(cambios)
    return datos


def alta(client, entorno, usuario=None, **cambios):
    respuesta = client.post(
        "/turnos",
        json=payload(entorno, **cambios),
        headers=cabecera(usuario or entorno.base.usuario),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_alta_lectura_y_reprogramacion_preservan_identidad(client, entorno):
    auth = cabecera(entorno.base.usuario)
    fila = alta(client, entorno)
    assert fila["estado"] == "reservado"
    assert "observaciones" not in fila and "telefono" not in fila
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila
    movido = client.post(
        f"/turnos/{fila['id']}/reprogramar",
        headers=auth,
        json={"nuevo_inicio": (INICIO + timedelta(hours=1)).isoformat()},
    )
    assert movido.status_code == 200, movido.text
    assert (movido.json()["id"], movido.json()["codigo_publico"], movido.json()["estado"]) == (
        fila["id"],
        fila["codigo_publico"],
        fila["estado"],
    )


def test_patch_y_accion_post_comparten_maquina(client, entorno):
    auth = cabecera(entorno.base.usuario)
    primero = alta(client, entorno)
    segundo = alta(client, entorno, inicio=(INICIO + timedelta(hours=1)).isoformat())
    patch = client.patch(f"/turnos/{primero['id']}", json={"estado": "confirmado"}, headers=auth)
    post = client.post(f"/turnos/{segundo['id']}/confirmar", headers=auth)
    assert patch.status_code == post.status_code == 200
    assert patch.json()["estado"] == post.json()["estado"] == "confirmado"
    assert (
        client.post(f"/turnos/{primero['id']}/atender", headers=auth).json()["estado"] == "atendido"
    )


def test_listado_profesional_es_propio(client, entorno):
    from app.db.models import EstadoTurno

    fila = asignar(entorno, EstadoTurno.RESERVADO)
    respuesta = client.get("/turnos", headers=cabecera(entorno.usuario))
    assert respuesta.status_code == 200
    assert [r["id"] for r in respuesta.json()] == [str(fila.id)]


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("GET", "/turnos"),
        ("POST", "/turnos"),
        ("PATCH", "/turnos/00000000-0000-0000-0000-000000000001"),
    ],
)
def test_operaciones_sin_jwt_rechazadas(client, metodo, ruta):
    assert client.request(metodo, ruta).status_code == 401


@pytest.mark.parametrize("actor", ["dueno", "recepcion"])
def test_recepcion_y_dueno_operan_todas_las_agendas(client, entorno, recepcion, actor):
    usuario = entorno.base.usuario if actor == "dueno" else recepcion
    fila = alta(client, entorno, usuario)
    respuesta = client.patch(
        f"/turnos/{fila['id']}", json={"estado": "confirmado"}, headers=cabecera(usuario)
    )
    assert respuesta.status_code == 200
    assert [r["id"] for r in client.get("/turnos", headers=cabecera(usuario)).json()] == [
        fila["id"]
    ]


def test_profesional_no_puede_autoasignarse_ficha_ajena(
    client, entorno, recepcion, session_factory
):
    auth = cabecera(entorno.usuario)
    rechazado = client.post("/turnos", json=payload(entorno), headers=auth)
    assert rechazado.status_code == 403 and rechazado.json()["code"] == "RN-AU-03"
    assert client.get(f"/pacientes/{entorno.base.paciente.id}", headers=auth).status_code == 403
    with session_factory() as session:
        assert session.query(Turno).count() == 0
    asignado = alta(client, entorno, recepcion)
    assert client.get(f"/pacientes/{entorno.base.paciente.id}", headers=auth).status_code == 200
    assert client.get(f"/turnos/{asignado['id']}", headers=auth).status_code == 200
    assert alta(client, entorno, entorno.usuario, inicio=(INICIO + timedelta(hours=1)).isoformat())[
        "profesional_id"
    ] == str(entorno.profesional.id)


def test_profesional_rechaza_otra_agenda_sin_mutaciones(client, entorno):
    asignar(entorno, EstadoTurno.RESERVADO)
    ajeno = alta(client, entorno, profesional_id=str(entorno.base.profesional.id))
    auth = cabecera(entorno.usuario)
    for respuesta in (
        client.get(f"/turnos/{ajeno['id']}", headers=auth),
        client.patch(f"/turnos/{ajeno['id']}", json={"estado": "confirmado"}, headers=auth),
        client.post(
            "/turnos",
            json=payload(
                entorno,
                profesional_id=str(entorno.base.profesional.id),
                inicio=(INICIO + timedelta(hours=1)).isoformat(),
            ),
            headers=auth,
        ),
        client.get(
            "/turnos", params={"profesional_id": str(entorno.base.profesional.id)}, headers=auth
        ),
    ):
        assert respuesta.status_code == 403 and respuesta.json()["code"] == "RN-AU-03"
    assert (
        client.get(f"/turnos/{ajeno['id']}", headers=cabecera(entorno.base.usuario)).json() == ajeno
    )


def test_profesional_sin_vinculo_no_abre_agenda(client, entorno, session_factory):
    with session_factory() as session:
        usuario = crear_usuario(
            session, entorno.base.tenant, "sinvinculo@demo", RolUsuario.PROFESIONAL
        )
    fila = alta(client, entorno)
    auth = cabecera(usuario)
    for respuesta in (
        client.get("/turnos", headers=auth),
        client.get(f"/turnos/{fila['id']}", headers=auth),
        client.post("/turnos", json=payload(entorno), headers=auth),
    ):
        assert respuesta.status_code == 403 and respuesta.json()["code"] == "RN-AU-03"


@pytest.mark.parametrize("campo", ["profesional_id", "paciente_id", "prestacion_id"])
def test_referencias_ajenas_y_lectura_id_otro_tenant_son404(
    client, entorno, session_factory, campo
):
    with session_factory() as session:
        ajeno = entorno_turnos(session, "otro")
    with tenant_context(ajeno.tenant.id, "otro"):
        fila = crear(TurnoCreate(**ajeno.datos()), ajeno.usuario, ahora=AHORA)
    auth = cabecera(entorno.base.usuario)
    for respuesta in (
        client.get(f"/turnos/{fila.id}", headers=auth),
        client.patch(f"/turnos/{fila.id}", json={"estado": "cancelado"}, headers=auth),
        client.post(
            "/turnos", json=payload(entorno, **{campo: str(ajeno.datos()[campo])}), headers=auth
        ),
    ):
        assert respuesta.status_code == 404
    with session_factory() as session:
        assert session.query(Turno).count() == 1
        assert session.get(Turno, fila.id).estado is EstadoTurno.RESERVADO


@pytest.mark.parametrize(
    "campo",
    [
        "inicio",
        "fin",
        "paciente_id",
        "profesional_id",
        "prestacion_id",
        "codigo_publico",
        "tenant_id",
        "es_sobreturno",
        "motivo_sobreturno",
        "otro",
    ],
)
def test_patch_extra_no_cambia_fila(client, entorno, campo):
    fila = alta(client, entorno)
    auth = cabecera(entorno.base.usuario)
    respuesta = client.patch(
        f"/turnos/{fila['id']}", json={"estado": "confirmado", campo: "invalido"}, headers=auth
    )
    assert respuesta.status_code == 422
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila


@pytest.mark.parametrize(
    "datos", [{}, {"estado": "confirmado", "motivo_cancelacion": "No"}, {"estado": "otro"}]
)
def test_patch_requiere_estado_y_motivo_coherente(client, entorno, datos):
    fila = alta(client, entorno)
    auth = cabecera(entorno.base.usuario)
    assert client.patch(f"/turnos/{fila['id']}", json=datos, headers=auth).status_code == 422
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila


@pytest.mark.parametrize(
    "accion", ["confirmar", "atender", "cancelar", "registrar-ausencia", "reprogramar"]
)
def test_acciones_rechazan_campos_inesperados_sin_efectos(client, entorno, accion):
    fila = alta(client, entorno)
    auth = cabecera(entorno.base.usuario)
    if accion in ("atender", "registrar-ausencia"):
        fila = client.post(f"/turnos/{fila['id']}/confirmar", headers=auth).json()
    cuerpo = {"fin": (INICIO + timedelta(hours=2)).isoformat()}
    if accion == "reprogramar":
        cuerpo["nuevo_inicio"] = (INICIO + timedelta(hours=1)).isoformat()
    assert (
        client.post(f"/turnos/{fila['id']}/{accion}", json=cuerpo, headers=auth).status_code == 422
    )
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila


def test_delete_no_borra_y_codigo_no_autentica(client, entorno):
    fila = alta(client, entorno)
    auth = cabecera(entorno.base.usuario)
    assert client.delete(f"/turnos/{fila['id']}", headers=auth).status_code == 405
    assert client.get(f"/turnos/{fila['id']}?codigo={fila['codigo_publico']}").status_code == 401
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila


def test_filtros_combinados_rango_semiabierto_y_orden_estable(client, entorno):
    auth = cabecera(entorno.base.usuario)
    primero = alta(client, entorno)
    segundo = alta(client, entorno, inicio=(INICIO + timedelta(hours=1)).isoformat())
    tercero = alta(client, entorno, inicio=(INICIO + timedelta(hours=2)).isoformat())
    otro = alta(client, entorno, profesional_id=str(entorno.base.profesional.id))
    assert client.post(f"/turnos/{segundo['id']}/confirmar", headers=auth).status_code == 200
    filas = client.get("/turnos", headers=auth).json()
    assert filas == sorted(filas, key=lambda r: (datetime.fromisoformat(r["inicio"]), r["id"]))
    assert {r["id"] for r in filas} == {primero["id"], segundo["id"], tercero["id"], otro["id"]}
    filtros = dict(
        profesional_id=str(entorno.profesional.id),
        estado="reservado",
        desde=INICIO.isoformat(),
        hasta=(INICIO + timedelta(hours=2)).isoformat(),
    )
    assert [r["id"] for r in client.get("/turnos", params=filtros, headers=auth).json()] == [
        primero["id"]
    ]
    pagina = client.get(
        "/turnos",
        params={"profesional_id": str(entorno.profesional.id), "limit": 1, "offset": 1},
        headers=auth,
    )
    assert [r["id"] for r in pagina.json()] == [segundo["id"]]


@pytest.mark.parametrize(
    "filtros",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"estado": "invalido"},
        {"profesional_id": "invalido"},
        {"desde": "2030-06-03T09:00:00"},
        {"desde": INICIO.isoformat(), "hasta": INICIO.isoformat()},
    ],
)
def test_filtros_invalidos_son422(client, entorno, filtros):
    assert (
        client.get("/turnos", params=filtros, headers=cabecera(entorno.base.usuario)).status_code
        == 422
    )


@pytest.mark.parametrize("campo", ["fin", "estado", "codigo_publico", "tenant_id", "id"])
def test_post_http_rechaza_campos_que_calcula_el_backend(client, entorno, session_factory, campo):
    assert (
        client.post(
            "/turnos",
            json=payload(entorno, **{campo: "no permitido"}),
            headers=cabecera(entorno.base.usuario),
        ).status_code
        == 422
    )
    with session_factory() as session:
        assert session.query(Turno).count() == 0


def test_reprogramacion_http_rechaza_fecha_sin_zona(client, entorno):
    fila = alta(client, entorno)
    auth = cabecera(entorno.base.usuario)
    respuesta = client.post(
        f"/turnos/{fila['id']}/reprogramar",
        headers=auth,
        json={"nuevo_inicio": "2030-06-03T10:00:00"},
    )
    assert respuesta.status_code == 422
    assert client.get(f"/turnos/{fila['id']}", headers=auth).json() == fila
