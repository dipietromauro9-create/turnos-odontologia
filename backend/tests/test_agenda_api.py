"""API real de agenda: contrato HTTP, roles y frontera de tenant."""

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import crear_token
from app.db.models import RolUsuario, Usuario
from tests.agenda_factories import crear_bloqueo, crear_disponibilidad
from tests.auth_helpers import app_de_prueba, cliente
from tests.factories import crear_usuario
from tests.test_disponibilidad_service import Entorno
from tests.test_disponibilidad_service import entorno as entorno

pytestmark = pytest.mark.integration


@pytest.fixture()
def app(entorno: Entorno) -> FastAPI:
    return app_de_prueba()[0]


def cabecera(usuario: Usuario) -> dict[str, str]:
    token = crear_token(
        sub=usuario.id,
        tenant_id=usuario.tenant_id,
        email=usuario.email,
        roles=[usuario.rol.value],
        tipo="access",
    )
    return {"Authorization": f"Bearer {token}"}


def payload(recurso: str, entorno: Entorno, **cambios: object) -> dict[str, object]:
    base = (
        {
            "profesional_id": str(entorno.profesional.id),
            "dia_semana": 0,
            "hora_desde": "09:00",
            "hora_hasta": "13:00",
        }
        if recurso == "disponibilidad"
        else {
            "profesional_id": None,
            "desde": "2026-11-03T09:00:00-03:00",
            "hasta": "2026-11-03T13:00:00-03:00",
            "motivo": "Cierre ficticio",
        }
    )
    return {**base, **cambios}


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_dueno_crea_lee_y_borra_y_recepcion_lee(
    app: FastAPI, entorno: Entorno, recurso: str
) -> None:
    client = cliente(app)
    creado = client.post(
        f"/{recurso}", json=payload(recurso, entorno), headers=cabecera(entorno.dueno)
    )
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["tenant_id"] == str(entorno.tenant.id)
    recepcion = client.get(f"/{recurso}", headers=cabecera(entorno.recepcion))
    assert recepcion.status_code == 200
    assert [r["id"] for r in recepcion.json()] == [cuerpo["id"]]
    borrado = client.delete(f"/{recurso}/{cuerpo['id']}", headers=cabecera(entorno.dueno))
    assert borrado.status_code == 204
    assert borrado.content == b""
    assert client.get(f"/{recurso}", headers=cabecera(entorno.dueno)).json() == []
    faltante = client.delete(f"/{recurso}/{cuerpo['id']}", headers=cabecera(entorno.dueno))
    assert faltante.status_code == 404
    assert faltante.json()["details"] == {"reason": "no_encontrado"}


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
@pytest.mark.parametrize("rol", ["recepcion", "usuario"])
def test_escritura_es_exclusiva_del_dueno(
    app: FastAPI, entorno: Entorno, recurso: str, rol: str
) -> None:
    client = cliente(app)
    creado = client.post(
        f"/{recurso}", json=payload(recurso, entorno), headers=cabecera(entorno.dueno)
    )
    assert creado.status_code == 201
    auth = cabecera(getattr(entorno, rol))
    for respuesta in (
        client.post(f"/{recurso}", json=payload(recurso, entorno), headers=auth),
        client.delete(f"/{recurso}/{creado.json()['id']}", headers=auth),
    ):
        assert respuesta.status_code == 403
        assert respuesta.json()["code"] == "RN-AU-02"
    assert len(client.get(f"/{recurso}", headers=cabecera(entorno.recepcion)).json()) == 1


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
@pytest.mark.parametrize("metodo", ["get", "post", "delete"])
def test_sin_token_es_401(app: FastAPI, entorno: Entorno, recurso: str, metodo: str) -> None:
    ruta = f"/{recurso}" + (f"/{uuid.uuid4()}" if metodo == "delete" else "")
    opciones = {"json": payload(recurso, entorno)} if metodo == "post" else {}
    respuesta = cliente(app).request(metodo, ruta, **opciones)
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "RN-AU-01"


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_profesional_lee_propios_y_globales_y_rechaza_filtro_ajeno(
    app: FastAPI, entorno: Entorno, recurso: str
) -> None:
    client = cliente(app)
    auth = cabecera(entorno.dueno)
    propio = client.post(
        f"/{recurso}",
        headers=auth,
        json=payload(recurso, entorno, profesional_id=str(entorno.profesional.id)),
    )
    ajeno = client.post(
        f"/{recurso}",
        headers=auth,
        json=payload(recurso, entorno, profesional_id=str(entorno.segundo.id)),
    )
    assert propio.status_code == ajeno.status_code == 201
    esperados = {propio.json()["id"]}
    if recurso == "bloqueos":
        global_ = client.post(f"/{recurso}", headers=auth, json=payload(recurso, entorno))
        assert global_.status_code == 201 and global_.json()["profesional_id"] is None
        esperados.add(global_.json()["id"])
    resultado = client.get(f"/{recurso}", headers=cabecera(entorno.usuario))
    assert resultado.status_code == 200
    assert {r["id"] for r in resultado.json()} == esperados
    prohibido = client.get(
        f"/{recurso}?profesional_id={entorno.segundo.id}", headers=cabecera(entorno.usuario)
    )
    assert prohibido.status_code == 403
    assert prohibido.json()["code"] == "RN-AU-03"


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_alta_ajena_y_borrado_inexistente_son_404(
    app: FastAPI, entorno: Entorno, recurso: str
) -> None:
    client = cliente(app)
    rechazado = client.post(
        f"/{recurso}",
        headers=cabecera(entorno.dueno),
        json=payload(recurso, entorno, profesional_id=str(entorno.ajeno.id)),
    )
    assert rechazado.status_code == 404
    assert client.get(f"/{recurso}", headers=cabecera(entorno.dueno)).json() == []
    assert (
        client.delete(f"/{recurso}/{uuid.uuid4()}", headers=cabecera(entorno.dueno)).status_code
        == 404
    )


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_rango_invalido_es_422(app: FastAPI, entorno: Entorno, recurso: str) -> None:
    cambio = (
        {"hora_hasta": "08:00"}
        if recurso == "disponibilidad"
        else {"hasta": "2026-11-03T08:00:00-03:00"}
    )
    respuesta = cliente(app).post(
        f"/{recurso}", json=payload(recurso, entorno, **cambio), headers=cabecera(entorno.dueno)
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == ("RN-AG-01" if recurso == "disponibilidad" else "RN-AG-02")


@pytest.mark.parametrize("hora_desde,hora_hasta", [("09:00", "13:00"), ("11:00", "15:00")])
def test_duplicado_y_solapado_son_409(
    app: FastAPI, entorno: Entorno, hora_desde: str, hora_hasta: str
) -> None:
    client = cliente(app)
    assert (
        client.post(
            "/disponibilidad",
            json=payload("disponibilidad", entorno),
            headers=cabecera(entorno.dueno),
        ).status_code
        == 201
    )
    respuesta = client.post(
        "/disponibilidad",
        json=payload("disponibilidad", entorno, hora_desde=hora_desde, hora_hasta=hora_hasta),
        headers=cabecera(entorno.dueno),
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["details"] == {"reason": "rango_solapado"}


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_otro_tenant_no_aparece_ni_se_puede_borrar(
    app: FastAPI, entorno: Entorno, recurso: str, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        fabrica = crear_disponibilidad if recurso == "disponibilidad" else crear_bloqueo
        ajeno = fabrica(session, entorno.otro_tenant, entorno.ajeno)
    client = cliente(app)
    auth = cabecera(entorno.dueno)
    assert client.get(f"/{recurso}", headers=auth).json() == []
    assert client.delete(f"/{recurso}/{ajeno.id}", headers=auth).status_code == 404
    with session_factory() as session:
        assert session.get(type(ajeno), ajeno.id) is not None


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_profesional_sin_vinculo_es_403(
    app: FastAPI, entorno: Entorno, recurso: str, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        usuario = crear_usuario(session, entorno.tenant, "sinvinculo@demo", RolUsuario.PROFESIONAL)
    respuesta = cliente(app).get(f"/{recurso}", headers=cabecera(usuario))
    assert respuesta.status_code == 403
    assert respuesta.json()["details"] == {"reason": "profesional_no_vinculado"}


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_dueno_lee_y_escribe_para_cualquier_profesional_del_tenant(
    app: FastAPI, entorno: Entorno, recurso: str
) -> None:
    client = cliente(app)
    auth = cabecera(entorno.dueno)
    for profesional in (entorno.profesional, entorno.segundo):
        respuesta = client.post(
            f"/{recurso}",
            headers=auth,
            json=payload(recurso, entorno, profesional_id=str(profesional.id)),
        )
        assert respuesta.status_code == 201
        lectura = client.get(f"/{recurso}?profesional_id={profesional.id}", headers=auth)
        assert lectura.status_code == 200
        assert [r["id"] for r in lectura.json()] == [respuesta.json()["id"]]


@pytest.mark.parametrize("recurso", ["disponibilidad", "bloqueos"])
def test_sin_token_no_se_ejecuta_el_servicio(
    app: FastAPI, entorno: Entorno, recurso: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.agenda.bloqueos import service as bloqueos
    from app.domain.agenda.disponibilidad import service as disponibilidad

    def no_debe_ejecutarse(*args: object) -> None:
        raise AssertionError("La request sin token llegó al servicio")

    monkeypatch.setattr(
        disponibilidad if recurso == "disponibilidad" else bloqueos, "crear", no_debe_ejecutarse
    )
    assert cliente(app).post(f"/{recurso}", json=payload(recurso, entorno)).status_code == 401


def test_guard_detecta_ruta_de_agenda_temporal_sin_roles(app: FastAPI) -> None:
    from tests.test_architecture import _rutas_sin_proteccion

    assert _rutas_sin_proteccion(app) == []

    @app.get("/disponibilidad/sin-roles")
    def sin_roles() -> dict[str, bool]:
        return {"ok": True}

    assert _rutas_sin_proteccion(app) == ["/disponibilidad/sin-roles"]


@pytest.mark.parametrize(
    "recurso,cambios",
    [
        ("disponibilidad", {"dia_semana": -1}),
        ("disponibilidad", {"dia_semana": 7}),
        ("disponibilidad", {"hora_desde": "09:00:00Z"}),
        ("bloqueos", {"desde": "2026-11-03T09:00:00"}),
        ("bloqueos", {"hasta": "2026-11-03T13:00:00"}),
        ("bloqueos", {"motivo": "   "}),
        ("disponibilidad", {"tenant_id": str(uuid.uuid4())}),
        ("bloqueos", {"tenant_id": str(uuid.uuid4())}),
    ],
)
def test_payload_invalido_es_422_sin_escribir(
    app: FastAPI, entorno: Entorno, recurso: str, cambios: dict[str, object]
) -> None:
    client = cliente(app)
    auth = cabecera(entorno.dueno)
    assert (
        client.post(
            f"/{recurso}", headers=auth, json=payload(recurso, entorno, **cambios)
        ).status_code
        == 422
    )
    assert client.get(f"/{recurso}", headers=auth).json() == []
