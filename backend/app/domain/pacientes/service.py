"""Servicio del dominio de pacientes (alta con advertencia y búsqueda)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, or_, select

from app.core.errors import DomainError
from app.db.models import Paciente, Usuario
from app.db.session import TenantSession
from app.domain.pacientes.dependencies import (
    AlcancePacientes,
    alcance_pacientes,
    exigir_acceso_paciente,
)
from app.domain.pacientes.schemas import (
    AdvertenciaDuplicado,
    PacienteCreate,
    PacienteIdentidadMinima,
    PacienteResumen,
    PacienteUpdate,
)
from app.domain.pacientes.telefono import normalizar_telefono, solo_digitos

RN_PA_01 = "RN-PA-01"
RN_PA_02 = "RN-PA-02"
RN_GL_01 = "RN-GL-01"

MENSAJE_DUPLICADO = "Ya existe un paciente con el mismo teléfono o nombre"

UMBRAL_SIMILITUD = 0.3
LARGO_MINIMO_TRIGRAM = 3
LIMITE_POR_DEFECTO = 20
LIMITE_MAXIMO = 100

CAMPOS_ACTUALIZABLES = frozenset({"nombre", "telefono", "documento", "fecha_nac", "observaciones"})
CAMPOS_NO_NULOS = ("nombre", "telefono")


@dataclass(frozen=True)
class ResultadoCreacion:
    paciente: Paciente
    advertencia: AdvertenciaDuplicado | None


@dataclass(frozen=True)
class ResultadoReutilizacion:
    """Contrato de C-09: identidad mínima para reservar, nunca la ficha."""

    identidad: PacienteIdentidadMinima
    creado: bool
    advertencia: AdvertenciaDuplicado | None


def _nombre_normalizado(nombre: str) -> str:
    return nombre.strip().lower()


def _buscar_duplicados(
    session: TenantSession,
    *,
    nombre: str,
    telefono: str,
    alcance: AlcancePacientes,
    usuario_id: uuid.UUID | None,
) -> list[Paciente]:
    """Coincidencias por teléfono normalizado o nombre normalizado dentro del alcance."""
    consulta = select(Paciente).where(Paciente.tenant_id == session.tenant_id)
    if alcance is AlcancePacientes.PROPIOS:
        if usuario_id is None:
            msg = "alcance PROPIOS requiere usuario_id"
            raise ValueError(msg)
        consulta = consulta.where(Paciente.creado_por_usuario_id == usuario_id)
    consulta = consulta.where(
        or_(
            Paciente.telefono == telefono,
            func.lower(func.trim(Paciente.nombre)) == _nombre_normalizado(nombre),
        )
    )
    return list(session.execute(consulta).scalars().all())


def _advertencia_duplicado(duplicados: list[Paciente]) -> AdvertenciaDuplicado:
    return AdvertenciaDuplicado(
        codigo=RN_PA_01,
        mensaje=MENSAJE_DUPLICADO,
        duplicados=[PacienteResumen.model_validate(duplicado) for duplicado in duplicados],
    )


def _nuevo_paciente(
    session: TenantSession,
    datos: PacienteCreate,
    usuario_id: uuid.UUID | None,
) -> Paciente:
    """Camino único de creación (panel y turnero): normaliza y persiste la ficha."""
    paciente = Paciente(
        tenant_id=session.tenant_id,
        nombre=datos.nombre,
        telefono=normalizar_telefono(datos.telefono),
        documento=datos.documento,
        fecha_nac=datos.fecha_nac,
        observaciones=datos.observaciones,
        creado_por_usuario_id=usuario_id,
    )
    session.add(paciente)
    session.flush()
    session.refresh(paciente)
    return paciente


def crear_paciente(
    session: TenantSession,
    datos: PacienteCreate,
    usuario: Usuario,
) -> ResultadoCreacion:
    """RN-PA-01: el alta nunca se bloquea; los duplicados se advierten (201)."""
    telefono = normalizar_telefono(datos.telefono)
    duplicados = _buscar_duplicados(
        session,
        nombre=datos.nombre,
        telefono=telefono,
        alcance=alcance_pacientes(usuario),
        usuario_id=usuario.id,
    )
    paciente = _nuevo_paciente(session, datos, usuario.id)
    advertencia = _advertencia_duplicado(duplicados) if duplicados else None
    return ResultadoCreacion(paciente=paciente, advertencia=advertencia)


def crear_o_reutilizar_paciente(
    session: TenantSession,
    *,
    nombre: str,
    telefono: str,
    usuario_id: uuid.UUID | None,
    alcance: AlcancePacientes,
) -> ResultadoReutilizacion:
    """Contrato de reserva que consume C-09: reutiliza por teléfono o crea.

    Devuelve solo `PacienteIdentidadMinima` (`id`, `nombre`, `telefono`), nunca
    `observaciones` ni la ficha completa (RN-PA-02). El turnero público pasa
    `usuario_id=None` y `AlcancePacientes.TODOS`; en ese caso la advertencia de
    duplicado viaja sin `duplicados` para no filtrar PII.
    """
    datos = PacienteCreate(nombre=nombre, telefono=telefono)
    consulta = select(Paciente).where(
        Paciente.tenant_id == session.tenant_id,
        Paciente.telefono == datos.telefono,
    )
    if alcance is AlcancePacientes.PROPIOS:
        if usuario_id is None:
            msg = "alcance PROPIOS requiere usuario_id"
            raise ValueError(msg)
        consulta = consulta.where(Paciente.creado_por_usuario_id == usuario_id)
    existente = session.execute(consulta.order_by(Paciente.creado_en)).scalars().first()
    if existente is not None:
        return ResultadoReutilizacion(
            identidad=PacienteIdentidadMinima.model_validate(existente),
            creado=False,
            advertencia=None,
        )

    duplicados = _buscar_duplicados(
        session,
        nombre=datos.nombre,
        telefono=datos.telefono,
        alcance=alcance,
        usuario_id=usuario_id,
    )
    paciente = _nuevo_paciente(session, datos, usuario_id)
    advertencia: AdvertenciaDuplicado | None = None
    if duplicados:
        advertencia = _advertencia_duplicado(duplicados)
        if usuario_id is None:
            advertencia = AdvertenciaDuplicado(codigo=RN_PA_01, mensaje=MENSAJE_DUPLICADO)
    return ResultadoReutilizacion(
        identidad=PacienteIdentidadMinima.model_validate(paciente),
        creado=True,
        advertencia=advertencia,
    )


def _condicion_trigram(texto: str) -> ColumnElement[bool]:
    """Operador `%` de pg_trgm: usa el umbral de similitud y el índice GIN."""
    return func.lower(Paciente.nombre).op("%")(texto)


def _consulta_busqueda(
    *,
    tenant_id: uuid.UUID,
    q: str | None,
    alcance: AlcancePacientes,
    usuario_id: uuid.UUID,
) -> tuple[Select[tuple[Paciente]], tuple[object, ...] | None]:
    """Construye la consulta y su orden; sin `q` solo ordena por nombre."""
    consulta = select(Paciente).where(Paciente.tenant_id == tenant_id)
    if alcance is AlcancePacientes.PROPIOS:
        consulta = consulta.where(Paciente.creado_por_usuario_id == usuario_id)

    termino = (q or "").strip()
    if not termino:
        return consulta, None

    texto = termino.lower()
    condiciones = []
    digitos = solo_digitos(termino)
    if digitos:
        condiciones.append(Paciente.telefono.like(f"%{digitos}%"))
    if len(texto) >= LARGO_MINIMO_TRIGRAM:
        condiciones.append(_condicion_trigram(texto))
    condiciones.append(func.lower(Paciente.nombre).like(f"%{texto}%"))
    consulta = consulta.where(or_(*condiciones))

    if len(texto) >= LARGO_MINIMO_TRIGRAM:
        orden = (func.similarity(func.lower(Paciente.nombre), texto).desc(), Paciente.nombre)
    else:
        orden = (Paciente.nombre,)
    return consulta, orden


def buscar_pacientes(
    session: TenantSession,
    *,
    q: str | None = None,
    alcance: AlcancePacientes,
    usuario_id: uuid.UUID,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> list[Paciente]:
    """RN-PA-01: busca por nombre (trigram + ILIKE) y teléfono normalizado."""
    limite = min(max(limit, 1), LIMITE_MAXIMO)
    desplazamiento = max(offset, 0)

    consulta, orden = _consulta_busqueda(
        tenant_id=session.tenant_id,
        q=q,
        alcance=alcance,
        usuario_id=usuario_id,
    )
    consulta = consulta.order_by(*(orden or (Paciente.nombre,)))
    consulta = consulta.limit(limite).offset(desplazamiento)
    return list(session.execute(consulta).scalars().all())


def eliminar_paciente(
    session: TenantSession,
    paciente_id: uuid.UUID,
    usuario: Usuario,
) -> bool:
    """Borra la fila físicamente; `False` si no existe en el tenant.

    Deuda explícita RN-PA-03 / DD-07 / IN-01: v1 no tiene soft delete ni
    registra auditoría (no hay tabla de auditoría); recuperar trazabilidad es
    prioridad post-MVP. C-05 no expone ninguna ruta HTTP de borrado.
    """
    consulta = select(Paciente).where(
        Paciente.id == paciente_id,
        Paciente.tenant_id == session.tenant_id,
    )
    paciente = session.execute(consulta).scalar_one_or_none()
    if paciente is None:
        return False
    exigir_acceso_paciente(usuario, paciente)
    session.delete(paciente)
    session.flush()
    return True


def _paciente_no_encontrado() -> DomainError:
    """404 `RN-PA-02`: el paciente no existe dentro del tenant resuelto."""
    return DomainError(
        RN_PA_02,
        "El paciente no existe",
        status_code=404,
        details={"reason": "no_encontrado"},
    )


def _obtener_en_tenant(session: TenantSession, paciente_id: uuid.UUID) -> Paciente:
    consulta = select(Paciente).where(
        Paciente.id == paciente_id,
        Paciente.tenant_id == session.tenant_id,
    )
    paciente = session.execute(consulta).scalar_one_or_none()
    if paciente is None:
        raise _paciente_no_encontrado()
    return paciente


def _validar_cambios(cambios: dict[str, object]) -> None:
    for campo in CAMPOS_NO_NULOS:
        if campo in cambios and cambios[campo] is None:
            raise DomainError(
                RN_GL_01,
                "El campo no puede ser nulo",
                status_code=422,
                details={"reason": "campo_invalido", "campo": campo},
            )


def obtener_paciente(
    session: TenantSession,
    paciente_id: uuid.UUID,
    usuario: Usuario,
) -> Paciente:
    """404 si no existe en el tenant; 403 `RN-AU-03` si existe fuera del alcance."""
    return exigir_acceso_paciente(usuario, _obtener_en_tenant(session, paciente_id))


def actualizar_paciente(
    session: TenantSession,
    paciente_id: uuid.UUID,
    datos: PacienteUpdate,
    usuario: Usuario,
) -> Paciente:
    """PATCH parcial: solo los campos enviados; nunca tenant ni creador."""
    paciente = exigir_acceso_paciente(usuario, _obtener_en_tenant(session, paciente_id))
    cambios = datos.model_dump(exclude_unset=True)
    _validar_cambios(cambios)
    for campo in CAMPOS_ACTUALIZABLES:
        if campo in cambios:
            setattr(paciente, campo, cambios[campo])
    session.flush()
    session.refresh(paciente)
    return paciente


__all__ = [
    "ResultadoCreacion",
    "ResultadoReutilizacion",
    "actualizar_paciente",
    "crear_o_reutilizar_paciente",
    "eliminar_paciente",
    "buscar_pacientes",
    "crear_paciente",
    "normalizar_telefono",
    "obtener_paciente",
    "solo_digitos",
]
