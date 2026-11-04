"""Cierres individuales y de consultorio con instantes conscientes de zona."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.db.session import tenant_context
from app.domain.agenda.bloqueos import service
from app.domain.agenda.bloqueos.schemas import BloqueoCreate, BloqueoPublic
from tests.test_disponibilidad_service import Entorno
from tests.test_disponibilidad_service import entorno as entorno

pytestmark = pytest.mark.integration
DESDE = datetime(2026, 11, 3, 9, tzinfo=UTC)


def datos(**cambios: object) -> BloqueoCreate:
    return BloqueoCreate.model_validate(
        {
            "desde": DESDE,
            "hasta": DESDE + timedelta(hours=1),
            "motivo": "Cierre ficticio",
            **cambios,
        }
    )


def test_cierre_global_conserva_nulo_y_es_visible_para_cualquier_profesional(
    entorno: Entorno,
) -> None:
    global_ = service.crear(datos())
    assert global_.profesional_id is None
    assert global_.tenant_id == entorno.tenant.id
    assert [b.id for b in service.listar(entorno.usuario)] == [global_.id]
    assert BloqueoPublic.model_validate(global_).desde.tzinfo is not None


def test_lectura_incluye_propios_y_globales_pero_no_individuales_ajenos(entorno: Entorno) -> None:
    global_ = service.crear(datos())
    propio = service.crear(datos(profesional_id=entorno.profesional.id))
    ajeno = service.crear(datos(profesional_id=entorno.segundo.id))
    esperado = sorted([global_.id, propio.id])
    assert [b.id for b in service.listar(entorno.usuario)] == esperado
    assert len(service.listar(entorno.recepcion)) == 3
    assert {b.id for b in service.listar(entorno.recepcion, entorno.segundo.id)} == {
        global_.id,
        ajeno.id,
    }


@pytest.mark.parametrize("hasta", [DESDE, DESDE - timedelta(seconds=1)])
def test_intervalo_invalido_no_se_persiste(entorno: Entorno, hasta: datetime) -> None:
    with pytest.raises(DomainError) as exc:
        service.crear(datos(hasta=hasta))
    assert (exc.value.status_code, exc.value.code) == (422, "RN-AG-02")
    assert exc.value.details == {"reason": "rango_invalido"}
    assert service.listar(entorno.dueno) == []


@pytest.mark.parametrize("campo", ["desde", "hasta"])
def test_instantes_sin_zona_se_rechazan(campo: str) -> None:
    with pytest.raises(ValidationError):
        datos(**{campo: datetime(2026, 11, 3, 9)})


@pytest.mark.parametrize("motivo", ["", "   "])
def test_motivo_no_puede_ser_vacio(motivo: str) -> None:
    with pytest.raises(ValidationError):
        datos(motivo=motivo)


def test_borrado_fisico_y_404_posterior(entorno: Entorno) -> None:
    creado = service.crear(datos())
    service.eliminar(creado.id)
    assert service.listar(entorno.dueno) == []
    with pytest.raises(DomainError) as exc:
        service.eliminar(creado.id)
    assert (exc.value.status_code, exc.value.code) == (404, "RN-AG-02")


def test_otro_tenant_no_se_lee_ni_borra_y_no_admite_su_profesional(entorno: Entorno) -> None:
    with tenant_context(entorno.otro_tenant.id, entorno.otro_tenant.slug):
        ajeno = service.crear(datos(profesional_id=entorno.ajeno.id))
    assert service.listar(entorno.recepcion) == []
    for identificador in (ajeno.id, uuid.uuid4()):
        with pytest.raises(DomainError) as exc:
            service.eliminar(identificador)
        assert exc.value.status_code == 404
    with pytest.raises(DomainError) as exc:
        service.crear(datos(profesional_id=entorno.ajeno.id))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("schema", [BloqueoCreate, BloqueoPublic])
def test_schemas_rechazan_extras(entorno: Entorno, schema: type) -> None:
    creado = service.crear(datos())
    payload = (
        datos().model_dump()
        if schema is BloqueoCreate
        else BloqueoPublic.model_validate(creado).model_dump()
    )
    with pytest.raises(ValidationError):
        schema.model_validate({**payload, "campo_ajeno": True})


def test_bloqueos_solapados_se_aceptan_y_se_ordenan(entorno: Entorno) -> None:
    primero = service.crear(datos(profesional_id=entorno.profesional.id))
    segundo = service.crear(
        datos(profesional_id=entorno.profesional.id, desde=DESDE + timedelta(minutes=30))
    )
    global_ = service.crear(datos())
    filas = service.listar(entorno.usuario)
    assert {b.id for b in filas} == {primero.id, segundo.id, global_.id}
    assert [(b.desde, b.id) for b in filas] == sorted((b.desde, b.id) for b in filas)
    assert global_.profesional_id is None


def test_profesional_ajeno_explicito_y_usuario_sin_vinculo_responden_403(entorno: Entorno) -> None:
    with pytest.raises(DomainError) as exc:
        service.listar(entorno.usuario, entorno.segundo.id)
    assert (exc.value.status_code, exc.value.code) == (403, "RN-AU-03")
    entorno.dueno.es_dueno = False
    with pytest.raises(DomainError) as exc:
        service.listar(entorno.dueno)
    assert exc.value.details == {"reason": "profesional_no_vinculado"}


def test_tenant_ajeno_conserva_sus_bloqueos_tras_el_intento_de_borrar(entorno: Entorno) -> None:
    with tenant_context(entorno.otro_tenant.id, entorno.otro_tenant.slug):
        ajeno = service.crear(datos())
    with pytest.raises(DomainError):
        service.eliminar(ajeno.id)
    with tenant_context(entorno.otro_tenant.id, entorno.otro_tenant.slug):
        assert [b.id for b in service.listar(entorno.recepcion)] == [ajeno.id]
