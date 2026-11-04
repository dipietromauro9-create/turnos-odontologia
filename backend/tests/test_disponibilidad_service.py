"""Disponibilidad: rango, intersección semiabierta y frontera de tenant."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, time

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import Profesional, RolUsuario, Tenant, Usuario
from app.db.session import tenant_context
from app.domain.agenda.disponibilidad import service
from app.domain.agenda.disponibilidad.schemas import DisponibilidadCreate, DisponibilidadPublic
from tests.agenda_factories import crear_profesional
from tests.factories import crear_tenant, crear_usuario

pytestmark = pytest.mark.integration


@dataclass
class Entorno:
    tenant: Tenant
    otro_tenant: Tenant
    profesional: Profesional
    segundo: Profesional
    ajeno: Profesional
    dueno: Usuario
    recepcion: Usuario
    usuario: Usuario


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> Iterator[Entorno]:
    with session_factory() as session:
        tenant = crear_tenant(session)
        otro_tenant = crear_tenant(session, "otro")
        dueno = crear_usuario(session, tenant, "dueno@demo", RolUsuario.PROFESIONAL, es_dueno=True)
        recepcion = crear_usuario(session, tenant, "recepcion@demo")
        usuario = crear_usuario(session, tenant, "profesional@demo", RolUsuario.PROFESIONAL)
        profesional = crear_profesional(session, tenant, usuario=usuario)
        segundo = crear_profesional(session, tenant)
        ajeno = crear_profesional(session, otro_tenant)
    with tenant_context(tenant.id, tenant.slug):
        yield Entorno(tenant, otro_tenant, profesional, segundo, ajeno, dueno, recepcion, usuario)


def datos(
    entorno: Entorno, desde: int = 9, hasta: int = 13, **cambios: object
) -> DisponibilidadCreate:
    payload = {
        "profesional_id": entorno.profesional.id,
        "dia_semana": 0,
        "hora_desde": time(desde),
        "hora_hasta": time(hasta),
    }
    payload.update(cambios)
    return DisponibilidadCreate.model_validate(payload)


@pytest.mark.parametrize("desde,hasta", [(13, 9), (9, 9)])
def test_rango_invalido_es_422_sin_persistir(entorno: Entorno, desde: int, hasta: int) -> None:
    with pytest.raises(DomainError) as exc:
        service.crear(datos(entorno, desde, hasta))
    assert (exc.value.status_code, exc.value.code) == (422, "RN-AG-01")
    assert exc.value.details == {"reason": "rango_invalido"}
    assert service.listar(entorno.recepcion) == []


@pytest.mark.parametrize("desde,hasta", [(9, 13), (11, 15)])
def test_duplicado_y_solapamiento_son_409(entorno: Entorno, desde: int, hasta: int) -> None:
    primero = service.crear(datos(entorno))
    with pytest.raises(DomainError) as exc:
        service.crear(datos(entorno, desde, hasta))
    assert (exc.value.status_code, exc.value.code) == (409, "RN-AG-01")
    assert exc.value.details == {"reason": "rango_solapado"}
    assert [r.id for r in service.listar(entorno.dueno)] == [primero.id]


def test_contiguas_y_otro_dia_profesional_son_validos(entorno: Entorno) -> None:
    primero = service.crear(datos(entorno))
    service.crear(datos(entorno, 13, 17))
    service.crear(datos(entorno, dia_semana=1))
    service.crear(datos(entorno, profesional_id=entorno.segundo.id))
    filas = service.listar(entorno.recepcion)
    assert len(filas) == 4
    assert [(r.dia_semana, r.hora_desde) for r in filas] == sorted(
        (r.dia_semana, r.hora_desde) for r in filas
    )
    assert DisponibilidadPublic.model_validate(primero).creado_en.tzinfo is not None


def test_referencia_de_otro_tenant_no_crea_filas(entorno: Entorno) -> None:
    with pytest.raises(DomainError) as exc:
        service.crear(datos(entorno, profesional_id=entorno.ajeno.id))
    assert exc.value.status_code == 404
    assert service.listar(entorno.recepcion) == []


def test_borrado_no_encuentra_id_ajeno_o_inexistente(entorno: Entorno) -> None:
    with tenant_context(entorno.otro_tenant.id, entorno.otro_tenant.slug):
        ajena = service.crear(datos(entorno, profesional_id=entorno.ajeno.id))
    for identificador in (ajena.id, uuid.uuid4()):
        with pytest.raises(DomainError) as exc:
            service.eliminar(identificador)
        assert exc.value.status_code == 404
        assert exc.value.details == {"reason": "no_encontrado"}
    assert service.listar(entorno.recepcion) == []


def test_eliminar_franja_la_quita_del_listado(entorno: Entorno) -> None:
    creada = service.crear(datos(entorno))
    service.eliminar(creada.id)
    assert service.listar(entorno.dueno) == []


@pytest.mark.parametrize("schema", [DisponibilidadCreate, DisponibilidadPublic])
def test_schemas_rechazan_campos_extra(entorno: Entorno, schema: type) -> None:
    creado = service.crear(datos(entorno))
    payload = (
        datos(entorno).model_dump()
        if schema is DisponibilidadCreate
        else DisponibilidadPublic.model_validate(creado).model_dump()
    )
    with pytest.raises(ValidationError):
        schema.model_validate({**payload, "no_declarado": True})


@pytest.mark.parametrize("desde,hasta", [(8, 14), (10, 12), (12, 14)])
def test_contencion_y_cruce_del_medio_se_rechazan(entorno: Entorno, desde: int, hasta: int) -> None:
    service.crear(datos(entorno, 6, 8))
    service.crear(datos(entorno, 9, 13))
    service.crear(datos(entorno, 15, 18))
    with pytest.raises(DomainError) as exc:
        service.crear(datos(entorno, desde, hasta))
    assert exc.value.status_code == 409
    assert len(service.listar(entorno.dueno)) == 3


def test_borde_de_dia_y_contiguas_por_ambos_extremos(entorno: Entorno) -> None:
    amplia = service.crear(datos(entorno, hora_desde=time(0), hora_hasta=time(23, 59)))
    assert amplia.hora_desde == time(0)
    service.eliminar(amplia.id)
    service.crear(datos(entorno, 9, 13))
    service.crear(datos(entorno, 6, 9))
    service.crear(datos(entorno, 13, 17))
    assert len(service.listar(entorno.dueno)) == 3


@pytest.mark.parametrize("campo", ["hora_desde", "hora_hasta"])
def test_horas_con_zona_son_invalidas(entorno: Entorno, campo: str) -> None:
    with pytest.raises(ValidationError):
        datos(entorno, **{campo: time(9, tzinfo=UTC)})


def test_profesional_solo_lee_lo_propio_y_filtro_ajeno_es_403(entorno: Entorno) -> None:
    propia = service.crear(datos(entorno))
    service.crear(datos(entorno, profesional_id=entorno.segundo.id))
    assert [r.id for r in service.listar(entorno.usuario)] == [propia.id]
    with pytest.raises(DomainError) as exc:
        service.listar(entorno.usuario, entorno.segundo.id)
    assert (exc.value.code, exc.value.status_code) == ("RN-AU-03", 403)


def test_profesional_sin_vinculo_es_403(entorno: Entorno) -> None:
    entorno.dueno.es_dueno = False
    with pytest.raises(DomainError) as exc:
        service.listar(entorno.dueno)
    assert exc.value.details == {"reason": "profesional_no_vinculado"}
