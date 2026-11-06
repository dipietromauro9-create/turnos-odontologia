"""Router público del turnero (catálogo, disponibilidad, reservas y autogestión)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime
from sqlalchemy import select

from app.core.errors import DomainError
from app.db.models import Prestacion, Profesional, Tenant
from app.db.session import (
    TenantContext,
    TenantNotFoundError,
    resolver_tenant_por_codigo_publico,
    system_session,
    tenant_context,
    tenant_session,
)
from app.domain.huecos.service import enumerar_huecos
from app.domain.turnero.rate_limit import RateLimiter, get_rate_limiter
from app.domain.turnero.schemas import (
    CancelarPublicoIn,
    CatalogoPublicoResponse,
    ConsultorioPublico,
    HuecoPublicoResponse,
    PrestacionPublica,
    ProfesionalPublico,
    ReprogramarPublicoIn,
    ReservaPublicaCreate,
    ReservaPublicaOut,
    TurnoPublicoOut,
)
from app.domain.turnos import service as turnos_service

RN_TU_06 = "RN-TU-06"
RN_GL_01 = "RN-GL-01"

RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocido"


def limitar_turnero(request: Request, limiter: RateLimiterDep) -> None:
    """10 req/min por IP en todo el canal público (RN-GL-01)."""
    cuota = limiter.consumir(_ip(request))
    if not cuota.permitido:
        raise DomainError(
            RN_GL_01,
            "Demasiadas solicitudes; esperá un momento antes de reintentar",
            status_code=429,
            details={"reason": "rate_limit", "retry_after": cuota.reintentar_en},
            headers={"Retry-After": str(cuota.reintentar_en)},
        )


router = APIRouter(
    prefix="/turnero",
    tags=["turnero-publico"],
    dependencies=[Depends(limitar_turnero)],
)


def get_tenant_por_slug(slug: str) -> Tenant:
    """Resuelve el consultorio por slug."""
    with system_session() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == slug)
        ).scalar_one_or_none()
    if tenant is None:
        raise DomainError(
            "RN-AG-01",
            "El consultorio no existe o no se encuentra activo",
            status_code=404,
            details={"slug": slug},
        )
    return tenant


TenantDep = Annotated[Tenant, Depends(get_tenant_por_slug)]


def _contexto_por_codigo(codigo: str) -> TenantContext:
    """Resuelve el tenant de un código público o responde 404 genérico (RN-TU-06)."""
    try:
        return resolver_tenant_por_codigo_publico(codigo)
    except TenantNotFoundError as exc:
        raise DomainError(
            RN_TU_06,
            "El turno no existe",
            status_code=404,
            details={"reason": "codigo_invalido"},
        ) from exc


def _detalle_out(detalle: turnos_service.TurnoPublicoDetalle) -> TurnoPublicoOut:
    turno = detalle.turno
    return TurnoPublicoOut(
        codigo_publico=turno.codigo_publico,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        profesional=ProfesionalPublico.model_validate(detalle.profesional),
        prestacion=PrestacionPublica.model_validate(detalle.prestacion),
    )


@router.get("/{slug}/catalogo", response_model=CatalogoPublicoResponse)
def obtener_catalogo_publico(tenant: TenantDep) -> CatalogoPublicoResponse:
    """Devuelve profesionales y prestaciones activas del consultorio."""
    with tenant_session(tenant.id) as session:
        profesionales = (
            session.execute(
                select(Profesional)
                .where(
                    Profesional.tenant_id == tenant.id,
                    Profesional.activo.is_(True),
                )
                .order_by(Profesional.nombre)
            )
            .scalars()
            .all()
        )
        prestaciones = (
            session.execute(
                select(Prestacion)
                .where(
                    Prestacion.tenant_id == tenant.id,
                    Prestacion.activa.is_(True),
                )
                .order_by(Prestacion.nombre)
            )
            .scalars()
            .all()
        )

    return CatalogoPublicoResponse(
        consultorio=ConsultorioPublico(nombre=tenant.nombre, slug=tenant.slug),
        profesionales=[
            ProfesionalPublico(id=p.id, nombre=p.nombre, especialidad=p.especialidad)
            for p in profesionales
        ],
        prestaciones=[
            PrestacionPublica(
                id=pr.id,
                nombre=pr.nombre,
                duracion_min=pr.duracion_min,
                precio_ref=pr.precio_ref,
            )
            for pr in prestaciones
        ],
    )


@router.get("/{slug}/disponibilidad", response_model=list[HuecoPublicoResponse])
def obtener_disponibilidad_publica(
    tenant: TenantDep,
    profesional_id: Annotated[uuid.UUID, Query(description="ID del profesional")],
    prestacion_id: Annotated[uuid.UUID, Query(description="ID de la prestación")],
    desde: Annotated[AwareDatetime, Query(description="Inicio del rango [desde, hasta)")],
    hasta: Annotated[AwareDatetime, Query(description="Fin del rango [desde, hasta)")],
) -> list[HuecoPublicoResponse]:
    """Calcula y devuelve los huecos libres para un profesional y prestación en el rango."""
    with tenant_context(tenant.id, tenant.slug):
        huecos = enumerar_huecos(
            profesional_id=profesional_id,
            prestacion_id=prestacion_id,
            desde=desde,
            hasta=hasta,
        )

    return [
        HuecoPublicoResponse(
            inicio=h.inicio,
            fin=h.fin,
            profesional_id=h.profesional_id,
            prestacion_id=h.prestacion_id,
        )
        for h in huecos
    ]


@router.post("/{slug}/reservas", status_code=201, response_model=ReservaPublicaOut)
def crear_reserva_publica(
    tenant: TenantDep,
    datos: ReservaPublicaCreate,
) -> ReservaPublicaOut:
    """Reserva anónima: paciente por teléfono + turno reservado con código público."""
    with tenant_context(tenant.id, tenant.slug):
        resultado = turnos_service.crear_publico(
            nombre=datos.nombre,
            telefono=datos.telefono,
            profesional_id=datos.profesional_id,
            prestacion_id=datos.prestacion_id,
            inicio=datos.inicio,
        )
    turno = resultado.turno
    return ReservaPublicaOut(
        codigo_publico=turno.codigo_publico,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        profesional_id=turno.profesional_id,
        prestacion_id=turno.prestacion_id,
        duplicado_advertencia=resultado.duplicado_advertencia,
    )


@router.get("/mis-turnos", response_model=TurnoPublicoOut)
def consultar_mis_turnos(
    codigo: Annotated[str, Query(min_length=1, max_length=64)],
) -> TurnoPublicoOut:
    """Consulta el turno propio por código, sin PII de terceros (RN-TU-06)."""
    contexto = _contexto_por_codigo(codigo)
    with tenant_context(contexto.tenant_id, contexto.slug):
        detalle = turnos_service.obtener_publico(codigo)
    return _detalle_out(detalle)


@router.post("/mis-turnos/cancelar", response_model=TurnoPublicoOut)
def cancelar_mi_turno(datos: CancelarPublicoIn) -> TurnoPublicoOut:
    """Cancela con código y motivo opcional, liberando el hueco (RN-TU-05)."""
    contexto = _contexto_por_codigo(datos.codigo)
    with tenant_context(contexto.tenant_id, contexto.slug):
        detalle = turnos_service.cancelar_publico(
            datos.codigo,
            datos.motivo_cancelacion,
        )
    return _detalle_out(detalle)


@router.post("/mis-turnos/reprogramar", response_model=TurnoPublicoOut)
def reprogramar_mi_turno(datos: ReprogramarPublicoIn) -> TurnoPublicoOut:
    """Reprograma de forma atómica; si el destino falla, el original queda intacto."""
    contexto = _contexto_por_codigo(datos.codigo)
    with tenant_context(contexto.tenant_id, contexto.slug):
        detalle = turnos_service.reprogramar_publico(
            datos.codigo,
            datos.nuevo_inicio,
        )
    return _detalle_out(detalle)
