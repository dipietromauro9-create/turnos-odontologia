"""Creación normal y urgencias sobre PostgreSQL real."""

from datetime import UTC, time, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DomainError
from app.db.models import Bloqueo, Disponibilidad, EstadoTurno, Profesional, Turno
from app.db.session import tenant_context
from app.domain.turnos.schemas import TurnoCreate
from app.domain.turnos.service import crear
from tests.factories import crear_profesional
from tests.turnos_factories import AHORA, INICIO, EntornoTurnos, entorno_turnos

pytestmark = pytest.mark.integration


@pytest.fixture()
def entorno(app_env: None, session_factory: sessionmaker[Session]) -> EntornoTurnos:
    with session_factory() as session:
        return entorno_turnos(session)


def test_alta_calcula_fin_y_nace_reservado(entorno: EntornoTurnos) -> None:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        fila = crear(TurnoCreate(**entorno.datos()), entorno.usuario, ahora=AHORA)
    assert fila.inicio == INICIO and fila.fin == INICIO + timedelta(minutes=30)
    assert fila.estado is EstadoTurno.RESERVADO and fila.tenant_id == entorno.tenant.id
    assert len(fila.codigo_publico) == 12


def test_fin_fuera_de_plantilla_rechaza_aunque_inicio_cabe(entorno: EntornoTurnos) -> None:
    with tenant_context(entorno.tenant.id, "demo"), pytest.raises(DomainError) as exc:
        crear(
            TurnoCreate(**entorno.datos(inicio=INICIO.replace(hour=12, minute=45))),
            entorno.usuario,
            ahora=AHORA,
        )
    assert (exc.value.code, exc.value.status_code) == ("RN-AG-01", 422)


def test_urgencia_fuera_de_plantilla_nace_confirmada(entorno: EntornoTurnos) -> None:
    with tenant_context(entorno.tenant.id, "demo"):
        fila = crear(
            TurnoCreate(
                **entorno.datos(
                    inicio=INICIO.replace(hour=18),
                    es_sobreturno=True,
                    motivo_sobreturno="Dolor ficticio",
                )
            ),
            entorno.usuario,
            ahora=AHORA,
        )
    assert fila.estado is EstadoTurno.CONFIRMADO
    assert fila.motivo_sobreturno == "Dolor ficticio"


def _alta(entorno: EntornoTurnos, **cambios: object) -> Turno:
    with tenant_context(entorno.tenant.id, entorno.tenant.slug):
        return crear(TurnoCreate(**entorno.datos(**cambios)), entorno.usuario, ahora=AHORA)


def _rechaza(
    entorno: EntornoTurnos,
    session_factory: sessionmaker[Session],
    code: str,
    status: int = 422,
    **cambios: object,
) -> None:
    with session_factory() as session:
        antes = session.query(Turno).count()
    with pytest.raises(DomainError) as exc:
        _alta(entorno, **cambios)
    assert (exc.value.code, exc.value.status_code) == (code, status)
    with session_factory() as session:
        assert session.query(Turno).count() == antes


@pytest.mark.parametrize("delta", [-1, 0])
def test_pasado_y_presente_no_crean_filas(entorno, session_factory, delta: int) -> None:
    _rechaza(entorno, session_factory, "RN-AG-01", inicio=AHORA + timedelta(seconds=delta))


def test_offset_equivalente_se_interpreta_en_zona_local(entorno) -> None:
    fila = _alta(entorno, inicio=INICIO.astimezone(UTC))
    assert fila.inicio == INICIO and fila.fin == INICIO + timedelta(minutes=30)


@pytest.mark.parametrize("contiguas", [False, True])
def test_franjas_contiguas_cubren_turno_pero_descanso_no(entorno, session_factory, contiguas):
    with session_factory() as session:
        franja = session.query(Disponibilidad).one()
        franja.hora_hasta = time(12)
        session.add(
            Disponibilidad(
                tenant_id=entorno.tenant.id,
                profesional_id=entorno.profesional.id,
                dia_semana=0,
                hora_desde=time(12 if contiguas else 13),
                hora_hasta=time(15),
            )
        )
        session.commit()
    if contiguas:
        assert _alta(entorno, inicio=INICIO.replace(hour=11, minute=45)).fin.hour == 12
    else:
        _rechaza(entorno, session_factory, "RN-AG-01", inicio=INICIO.replace(hour=11, minute=45))


def test_cruce_de_medianoche_sin_cobertura_completa_se_rechaza(entorno, session_factory):
    with session_factory() as session:
        franja = session.query(Disponibilidad).one()
        franja.hora_desde, franja.hora_hasta = time(23), time(23, 59)
        session.add(
            Disponibilidad(
                tenant_id=entorno.tenant.id,
                profesional_id=entorno.profesional.id,
                dia_semana=1,
                hora_desde=time(0),
                hora_hasta=time(2),
            )
        )
        session.commit()
    _rechaza(entorno, session_factory, "RN-AG-01", inicio=INICIO.replace(hour=23, minute=45))


@pytest.mark.parametrize(
    "tipo", ["global", "personal", "otro", "contiguo_antes", "contiguo_despues"]
)
@pytest.mark.parametrize("urgencia", [False, True])
def test_bloqueos_personales_globales_y_bordes(entorno, session_factory, tipo, urgencia):
    with session_factory() as session:
        profesional_id = None
        if tipo != "global":
            profesional_id = entorno.profesional.id
        if tipo == "otro":
            profesional_id = crear_profesional(session, entorno.tenant).id
        desde, hasta = INICIO - timedelta(minutes=15), INICIO + timedelta(minutes=15)
        if tipo == "contiguo_antes":
            hasta = INICIO
        elif tipo == "contiguo_despues":
            desde, hasta = INICIO + timedelta(minutes=30), INICIO + timedelta(hours=1)
        session.add(
            Bloqueo(
                tenant_id=entorno.tenant.id,
                profesional_id=profesional_id,
                desde=desde,
                hasta=hasta,
                motivo="Cierre ficticio",
            )
        )
        session.commit()
    datos = dict(es_sobreturno=urgencia, motivo_sobreturno="Dolor" if urgencia else None)
    if tipo in ("global", "personal"):
        _rechaza(entorno, session_factory, "RN-AG-02", 409, **datos)
    else:
        assert _alta(entorno, **datos).id is not None


@pytest.mark.parametrize(
    "datos",
    [
        {"es_sobreturno": True},
        {"es_sobreturno": True, "motivo_sobreturno": " "},
        {"motivo_sobreturno": "Dolor"},
        {"es_sobreturno": False, "motivo_sobreturno": "Dolor"},
    ],
)
def test_flag_y_motivo_siempre_explicitos(entorno, session_factory, datos):
    _rechaza(entorno, session_factory, "RN-TU-03", **datos)


@pytest.mark.parametrize("referencia", ["profesional_id", "paciente_id", "prestacion_id"])
def test_referencias_de_otro_tenant_no_crean_ni_revelan(entorno, session_factory, referencia):
    with session_factory() as session:
        ajeno = entorno_turnos(session, "otro")
    _rechaza(entorno, session_factory, "RN-TU-01", 404, **{referencia: ajeno.datos()[referencia]})


@pytest.mark.parametrize("catalogo", ["profesional", "prestacion"])
def test_catalogo_inactivo_no_se_reserva(entorno, session_factory, catalogo):
    with session_factory() as session:
        modelo = Profesional if catalogo == "profesional" else type(entorno.prestacion)
        fila = session.get(modelo, getattr(entorno, catalogo).id)
        setattr(fila, "activo" if catalogo == "profesional" else "activa", False)
        session.commit()
    _rechaza(entorno, session_factory, "RN-TU-02")


@pytest.mark.parametrize("extra", ["fin", "estado", "codigo_publico", "tenant_id", "autor_id"])
def test_creacion_prohibe_campos_calculados(extra):
    import uuid

    from pydantic import ValidationError

    datos = dict(
        profesional_id=uuid.uuid4(),
        paciente_id=uuid.uuid4(),
        prestacion_id=uuid.uuid4(),
        inicio=INICIO,
        **{extra: "invalido"},
    )
    with pytest.raises(ValidationError):
        TurnoCreate(**datos)


def test_inicio_sin_zona_horaria_se_rechaza():
    import uuid

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TurnoCreate(
            profesional_id=uuid.uuid4(),
            paciente_id=uuid.uuid4(),
            prestacion_id=uuid.uuid4(),
            inicio=INICIO.replace(tzinfo=None),
        )


def test_consulta_previa_rechaza_ocupacion_y_sobreturno(entorno, session_factory):
    _alta(entorno)
    _rechaza(entorno, session_factory, "RN-TU-01", 409, inicio=INICIO + timedelta(minutes=15))
    _rechaza(
        entorno, session_factory, "RN-TU-01", 409, es_sobreturno=True, motivo_sobreturno="Dolor"
    )


def test_colision_codigo_reintenta_sin_fila_parcial(entorno, session_factory, monkeypatch):
    primero = _alta(entorno)
    codigos = iter([primero.codigo_publico, "codigo_libre"])
    monkeypatch.setattr("app.domain.turnos.service.generar_codigo", lambda: next(codigos))
    segundo = _alta(entorno, inicio=INICIO + timedelta(hours=1))
    assert segundo.codigo_publico == "codigo_libre" and segundo.id != primero.id
    with session_factory() as session:
        assert session.query(Turno).count() == 2


def test_codigo_agotado_limita_intentos_y_no_crea_nada(entorno, session_factory, monkeypatch):
    primero = _alta(entorno)
    llamadas = []

    def repetido():
        llamadas.append(1)
        return primero.codigo_publico

    monkeypatch.setattr("app.domain.turnos.service.generar_codigo", repetido)
    _rechaza(entorno, session_factory, "RN-GL-01", 409, inicio=INICIO + timedelta(hours=1))
    assert len(llamadas) == 5


def test_otra_integridad_no_se_traduce_ni_reintenta(entorno, monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.domain.turnos.repository import TurnosRepository

    class OtroError(Exception):
        diag = SimpleNamespace(constraint_name="fk_ajena")

    fallo = IntegrityError("INSERT", {}, OtroError())
    llamadas = []

    def fallar(*args):
        llamadas.append(1)
        raise fallo

    monkeypatch.setattr(TurnosRepository, "add", fallar)
    with pytest.raises(IntegrityError) as exc:
        _alta(entorno)
    assert exc.value is fallo and len(llamadas) == 1


@pytest.mark.parametrize("sqlstate,intentos", [("08006", 1), ("40P01", 3)])
def test_retry_solo_deadlock_y_limite_estricto(entorno, monkeypatch, sqlstate, intentos):
    from sqlalchemy.exc import OperationalError

    class ErrorDriver(Exception):
        pass

    origen = ErrorDriver()
    origen.sqlstate = sqlstate
    fallo = OperationalError("INSERT", {}, origen)
    llamadas = []

    def fallar(*args, **kwargs):
        llamadas.append(1)
        raise fallo

    monkeypatch.setattr("app.domain.turnos.service._validar_candidato", fallar)
    with pytest.raises(OperationalError) as exc:
        _alta(entorno)
    assert exc.value is fallo and len(llamadas) == intentos
