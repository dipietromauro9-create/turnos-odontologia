"""Único camino de escritura de turnos: RN-TU y unidad de trabajo atómica."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.errors import DomainError
from app.core.settings import get_settings
from app.db.models import EstadoTurno, Paciente, Prestacion, Profesional, Turno, Usuario
from app.db.models.turno import EXCLUSION_OCUPACION, UNIQUE_CODIGO
from app.domain.agenda.alcance import profesional_del_alcance
from app.domain.pacientes.dependencies import AlcancePacientes, exigir_acceso_paciente
from app.domain.pacientes.service import crear_o_reutilizar_paciente
from app.domain.persistence import UnitOfWork
from app.domain.turnos.codigos import generar_codigo
from app.domain.turnos.estados import validar_transicion
from app.domain.turnos.repository import TurnosRepository
from app.domain.turnos.schemas import TurnoCreate, TurnoFiltros


def error(code: str, reason: str, status: int = 422) -> DomainError:
    mensajes = {
        "no_encontrado": "El turno o una referencia no existe",
        "referencia_inactiva": "El profesional o la prestación está desactivado",
        "horario_no_habilitado": "El horario debe ser futuro y estar dentro de disponibilidad",
        "bloqueado": "El horario está bloqueado",
        "ocupado": "El horario ya está ocupado",
        "sobreturno_incoherente": "El sobreturno requiere flag y motivo de urgencia",
        "codigo_no_disponible": "No se pudo generar un código disponible",
        "estado_terminal": "Un turno terminal no puede reprogramarse",
        "codigo_invalido": "El turno no existe",
    }
    return DomainError(code, mensajes[reason], status, details={"reason": reason})



def _reintentar_deadlock[**P, R](operacion: Callable[P, R]) -> Callable[P, R]:
    """Postgres puede abortar un participante de EXCLUDE con SQLSTATE 40P01.

    Repetir el UoW entero desde una sesión nueva permite revalidar el horario
    contra el ganador. No se confunden errores de conexión con conflictos.
    """

    @wraps(operacion)
    def ejecutar(*args: P.args, **kwargs: P.kwargs) -> R:
        for intento in range(3):
            try:
                return operacion(*args, **kwargs)
            except OperationalError as exc:
                if getattr(exc.orig, "sqlstate", None) != "40P01" or intento == 2:
                    raise
        raise AssertionError("ciclo de reintentos inválido")

    return ejecutar


def _cubierto(
    repo: TurnosRepository, profesional_id: uuid.UUID, inicio: datetime, fin: datetime
) -> bool:
    cursor = inicio
    while cursor < fin:
        medianoche = datetime.combine(cursor.date() + timedelta(days=1), time(), cursor.tzinfo)
        extremo = min(fin, medianoche)
        cubierto = cursor
        for franja in repo.franjas(profesional_id, cursor.weekday()):
            desde = datetime.combine(cursor.date(), franja.hora_desde, cursor.tzinfo)
            hasta = datetime.combine(cursor.date(), franja.hora_hasta, cursor.tzinfo)
            if hasta <= cubierto:
                continue
            if desde > cubierto:
                break
            cubierto = hasta
            if cubierto >= extremo:
                break
        if cubierto < extremo:
            return False
        cursor = extremo
    return True


def _validar_candidato(
    repo: TurnosRepository,
    profesional_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
    sobreturno: bool,
    ahora: datetime,
    excluir: uuid.UUID | None = None,
) -> None:
    tz = ZoneInfo(get_settings().tz)
    inicio, fin = inicio.astimezone(tz), fin.astimezone(tz)
    if inicio <= ahora or not sobreturno and not _cubierto(repo, profesional_id, inicio, fin):
        raise error("RN-AG-01", "horario_no_habilitado")
    if repo.bloqueado(profesional_id, inicio, fin):
        raise error("RN-AG-02", "bloqueado", 409)
    if repo.ocupado(profesional_id, inicio, fin, excluir):
        raise error("RN-TU-01", "ocupado", 409)


@dataclass(frozen=True)
class ResultadoEjemplo:
    turno: Turno
    creado: bool


@dataclass(frozen=True)
class ResultadoReservaPublica:
    """Reserva anónima: turno creado y advertencia de homónimo para recepción."""

    turno: Turno
    duplicado_advertencia: bool


@dataclass(frozen=True)
class TurnoPublicoDetalle:
    """Turno con sus referencias públicas, sin datos del paciente (RN-AG-04)."""

    turno: Turno
    profesional: Profesional
    prestacion: Prestacion


def _normalizar_nombre(nombre: str) -> str:
    return " ".join(nombre.strip().lower().split())


def _insertar_turno(
    uow: UnitOfWork,
    repo: TurnosRepository,
    *,
    id_: uuid.UUID | None = None,
    **campos: object,
) -> Turno:
    """Inserta con reintento de código; traduce `EXCLUDE` a 409 RN-TU-01."""
    for _ in range(5):
        try:
            with uow.session.begin_nested():
                fila = repo.add(
                    Turno(
                        **({"id": id_} if id_ is not None else {}),
                        **campos,
                        codigo_publico=generar_codigo(),
                    )
                )
            uow.session.refresh(fila)
            return fila
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == EXCLUSION_OCUPACION:
                raise error("RN-TU-01", "ocupado", 409) from exc
            if constraint != UNIQUE_CODIGO:
                raise
    raise error("RN-GL-01", "codigo_no_disponible", 409)


def _detalle(uow: UnitOfWork, fila: Turno) -> TurnoPublicoDetalle:
    profesional = uow.repository(Profesional).get(fila.profesional_id)
    prestacion = uow.repository(Prestacion).get(fila.prestacion_id)
    if profesional is None or prestacion is None:
        raise error("RN-TU-01", "no_encontrado", 404)
    return TurnoPublicoDetalle(turno=fila, profesional=profesional, prestacion=prestacion)



def crear(datos: TurnoCreate, usuario: Usuario, *, ahora: datetime | None = None) -> Turno:
    return _crear(datos, usuario, ahora=ahora).turno


def crear_ejemplo(
    identificador: uuid.UUID,
    datos: TurnoCreate,
    usuario: Usuario,
    destino: EstadoTurno,
    *,
    ahora: datetime | None = None,
) -> ResultadoEjemplo:
    """Entrada interna idempotente del seed; ningún payload HTTP admite estos controles."""
    if destino not in (EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO, EstadoTurno.ATENDIDO):
        raise ValueError("Estado de ejemplo inválido")
    return _crear(datos, usuario, ahora=ahora, identificador=identificador, destino=destino)


@_reintentar_deadlock
def crear_publico(
    *,
    nombre: str,
    telefono: str,
    profesional_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    inicio: datetime,
    ahora: datetime | None = None,
) -> ResultadoReservaPublica:
    """Reserva anónima (C-09) por el único camino de escritura de turnos (R4).

    Busca o crea el paciente por teléfono (RN-PA-01), calcula `fin` en backend
    (RN-TU-02) y delega el anti-solape al servicio/constraint (RN-TU-01). Todo
    ocurre en una sola unidad de trabajo: si el turno falla, no queda paciente
    huérfano.
    """
    with UnitOfWork() as uow:
        repo = TurnosRepository(uow.session)
        profesional = uow.repository(Profesional).get(profesional_id)
        prestacion = uow.repository(Prestacion).get(prestacion_id)
        if profesional is None or prestacion is None:
            raise error("RN-TU-01", "no_encontrado", 404)
        if not profesional.activo or not prestacion.activa:
            raise error("RN-TU-02", "referencia_inactiva")
        fin = inicio + timedelta(minutes=prestacion.duracion_min)
        _validar_candidato(repo, profesional.id, inicio, fin, False, ahora or datetime.now(UTC))
        paciente = crear_o_reutilizar_paciente(
            uow.session,
            nombre=nombre,
            telefono=telefono,
            usuario_id=None,
            alcance=AlcancePacientes.TODOS,
        )
        fila = _insertar_turno(
            uow,
            repo,
            profesional_id=profesional.id,
            paciente_id=paciente.identidad.id,
            prestacion_id=prestacion.id,
            inicio=inicio,
            fin=fin,
            estado=EstadoTurno.RESERVADO,
            es_sobreturno=False,
            motivo_sobreturno=None,
        )
        advertencia = bool(paciente.advertencia) or (
            not paciente.creado
            and _normalizar_nombre(paciente.identidad.nombre) != _normalizar_nombre(nombre)
        )
        return ResultadoReservaPublica(turno=fila, duplicado_advertencia=advertencia)


def _obtener_por_codigo(uow: UnitOfWork, codigo: str, *, bloquear: bool = False) -> Turno:
    fila = TurnosRepository(uow.session).por_codigo(codigo, bloquear=bloquear)
    if fila is None:
        raise error("RN-TU-06", "codigo_invalido", 404)
    return fila


def obtener_publico(codigo: str) -> TurnoPublicoDetalle:
    """Consulta de autogestión por código (RN-TU-06); nunca revela si no existe."""
    with UnitOfWork() as uow:
        return _detalle(uow, _obtener_por_codigo(uow, codigo))


@_reintentar_deadlock
def cancelar_publico(codigo: str, motivo: str | None = None) -> TurnoPublicoDetalle:
    """Cancelación autónoma (RN-TU-05) con la máquina RN-TU-04 vigente."""
    with UnitOfWork() as uow:
        fila = _obtener_por_codigo(uow, codigo, bloquear=True)
        validar_transicion(fila.estado, EstadoTurno.CANCELADO)
        fila.estado = EstadoTurno.CANCELADO
        fila.motivo_cancelacion = motivo
        uow.session.flush()
        uow.session.refresh(fila)
        return _detalle(uow, fila)


@_reintentar_deadlock
def reprogramar_publico(
    codigo: str,
    nuevo_inicio: datetime,
    *,
    ahora: datetime | None = None,
) -> TurnoPublicoDetalle:
    """Reprogramación atómica por código (RN-TU-07); si falla, el original queda intacto."""
    with UnitOfWork() as uow:
        fila = _obtener_por_codigo(uow, codigo, bloquear=True)
        _aplicar_reprogramacion(uow, fila, nuevo_inicio, ahora)
        return _detalle(uow, fila)


@_reintentar_deadlock
def _crear(
    datos: TurnoCreate,
    usuario: Usuario,
    *,
    ahora: datetime | None = None,
    identificador: uuid.UUID | None = None,
    destino: EstadoTurno | None = None,
) -> ResultadoEjemplo:
    motivo = datos.motivo_sobreturno
    if (datos.es_sobreturno and not motivo) or (not datos.es_sobreturno and motivo is not None):
        raise error("RN-TU-03", "sobreturno_incoherente")
    with UnitOfWork() as uow:
        repo = TurnosRepository(uow.session)
        if identificador is not None:
            existente = repo.get(identificador)
            if existente is not None:
                return ResultadoEjemplo(existente, False)
        profesional = uow.repository(Profesional).get(datos.profesional_id)
        paciente = uow.repository(Paciente).get(datos.paciente_id)
        prestacion = uow.repository(Prestacion).get(datos.prestacion_id)
        if profesional is None or paciente is None or prestacion is None:
            raise error("RN-TU-01", "no_encontrado", 404)
        if not profesional.activo or not prestacion.activa:
            raise error("RN-TU-02", "referencia_inactiva")
        profesional_del_alcance(uow.session, usuario, profesional.id)
        exigir_acceso_paciente(usuario, paciente, uow.session)
        fin = datos.inicio + timedelta(minutes=prestacion.duracion_min)
        _validar_candidato(
            repo, profesional.id, datos.inicio, fin, datos.es_sobreturno, ahora or datetime.now(UTC)
        )
        fila = _insertar_turno(
            uow,
            repo,
            id_=identificador,
            **datos.model_dump(),
            fin=fin,
            estado=EstadoTurno.CONFIRMADO if datos.es_sobreturno else EstadoTurno.RESERVADO,
        )
        if destino in (EstadoTurno.CONFIRMADO, EstadoTurno.ATENDIDO):
            if fila.estado is EstadoTurno.RESERVADO:
                validar_transicion(fila.estado, EstadoTurno.CONFIRMADO)
                fila.estado = EstadoTurno.CONFIRMADO
            if destino is EstadoTurno.ATENDIDO:
                validar_transicion(fila.estado, destino)
                fila.estado = destino
            uow.session.flush()
            uow.session.refresh(fila)
        return ResultadoEjemplo(fila, True)


def _obtener_para_escribir(uow: UnitOfWork, identificador: uuid.UUID, usuario: Usuario) -> Turno:
    fila = TurnosRepository(uow.session).obtener_bloqueado(identificador)
    if fila is None:
        raise error("RN-TU-01", "no_encontrado", 404)
    profesional_del_alcance(uow.session, usuario, fila.profesional_id)
    return fila


def obtener(identificador: uuid.UUID, usuario: Usuario) -> Turno:
    with UnitOfWork() as uow:
        fila = TurnosRepository(uow.session).get(identificador)
        if fila is None:
            raise error("RN-TU-01", "no_encontrado", 404)
        profesional_del_alcance(uow.session, usuario, fila.profesional_id)
        return fila


def listar(usuario: Usuario, filtros: TurnoFiltros) -> list[Turno]:
    with UnitOfWork() as uow:
        profesional_id = profesional_del_alcance(uow.session, usuario, filtros.profesional_id)
        return TurnosRepository(uow.session).consultar(filtros, profesional_id)


@_reintentar_deadlock
def transicionar(
    identificador: uuid.UUID,
    destino: EstadoTurno,
    usuario: Usuario,
    *,
    motivo_cancelacion: str | None = None,
) -> Turno:
    with UnitOfWork() as uow:
        fila = _obtener_para_escribir(uow, identificador, usuario)
        validar_transicion(fila.estado, destino)
        if motivo_cancelacion is not None and destino is not EstadoTurno.CANCELADO:
            raise DomainError(
                "RN-TU-04",
                "El motivo solo corresponde a una cancelación",
                422,
                details={"reason": "motivo_incompatible"},
            )
        fila.estado = destino
        if destino is EstadoTurno.CANCELADO:
            fila.motivo_cancelacion = motivo_cancelacion
        uow.session.flush()
        uow.session.refresh(fila)
        return fila


def _aplicar_reprogramacion(
    uow: UnitOfWork,
    fila: Turno,
    nuevo_inicio: datetime,
    ahora: datetime | None,
) -> None:
    if fila.estado not in (EstadoTurno.RESERVADO, EstadoTurno.CONFIRMADO):
        raise error("RN-TU-04", "estado_terminal")
    nuevo_fin = nuevo_inicio + (fila.fin - fila.inicio)
    _validar_candidato(
        TurnosRepository(uow.session),
        fila.profesional_id,
        nuevo_inicio,
        nuevo_fin,
        fila.es_sobreturno,
        ahora or datetime.now(UTC),
        excluir=fila.id,
    )
    fila.inicio, fila.fin = nuevo_inicio, nuevo_fin
    try:
        uow.session.flush()
    except IntegrityError as exc:
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == EXCLUSION_OCUPACION
        ):
            raise error("RN-TU-01", "ocupado", 409) from exc
        raise
    uow.session.refresh(fila)


@_reintentar_deadlock
def reprogramar(
    identificador: uuid.UUID,
    nuevo_inicio: datetime,
    usuario: Usuario,
    *,
    ahora: datetime | None = None,
) -> Turno:
    with UnitOfWork() as uow:
        fila = _obtener_para_escribir(uow, identificador, usuario)
        _aplicar_reprogramacion(uow, fila, nuevo_inicio, ahora)
        return fila
