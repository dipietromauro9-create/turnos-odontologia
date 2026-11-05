"""Guardas que pueden fallar ante escrituras laterales o exposición pública."""

from pathlib import Path

from fastapi import FastAPI

from app.domain.turnos.schemas import TurnoPublic
from tests.test_architecture import app_del_panel as app_del_panel
from tests.turnos_boundary import escrituras_fuera_del_servicio, rutas_publicas_que_exponen_turnos

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_guard_r4_detecta_constructor_y_asignacion_fuera_del_servicio(tmp_path):
    dominio = tmp_path / "domain"
    dominio.mkdir()
    (dominio / "externo.py").write_text(
        'from app.db.models import Turno as Cita\nfila = Cita(estado="reservado")\n',
        encoding="utf-8",
    )
    (dominio / "otro.py").write_text(
        'from app.db.models import Turno\nturno.estado = "cancelado"\n', encoding="utf-8"
    )
    assert set(escrituras_fuera_del_servicio(tmp_path)) == {"domain/externo.py", "domain/otro.py"}


def test_guard_r4_permite_servicio_y_consultas(tmp_path):
    servicio = tmp_path / "domain" / "turnos"
    servicio.mkdir(parents=True)
    (servicio / "service.py").write_text(
        "from app.db.models import Turno\nfila=Turno()\n", encoding="utf-8"
    )
    (servicio / "repository.py").write_text(
        "from app.db.models import Turno\nselect(Turno)\n", encoding="utf-8"
    )
    assert escrituras_fuera_del_servicio(tmp_path) == []


def test_guard_r4_app_real_y_catalogo_permanecen_protegidos():
    from tests.test_architecture import infracciones_turno_en_agenda

    assert escrituras_fuera_del_servicio(APP_DIR) == []
    assert infracciones_turno_en_agenda() == []


def test_frontera_detecta_un_schema_de_turno_en_ruta_publica():
    app = FastAPI()

    @app.get("/turnero/demo")
    def expuesto() -> TurnoPublic:
        raise NotImplementedError

    assert rutas_publicas_que_exponen_turnos(app) == ["/turnero/demo"]


def test_frontera_permite_health_y_huecos_publicos():
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/turnero/demo")
    def huecos() -> list[str]:
        return []

    assert rutas_publicas_que_exponen_turnos(app) == []


def test_frontera_app_real(app_del_panel):
    assert rutas_publicas_que_exponen_turnos(app_del_panel) == []


def test_openapi_expone_contrato_restringido_y_nueve_operaciones(app_del_panel):
    esquema = app_del_panel.openapi()
    paths = esquema["paths"]
    assert set(paths["/turnos"]) == {"get", "post"}
    assert set(paths["/turnos/{identificador}"]) == {"get", "patch"}
    acciones = {"confirmar", "atender", "cancelar", "registrar-ausencia", "reprogramar"}
    for accion in acciones:
        assert set(paths[f"/turnos/{{identificador}}/{accion}"]) == {"post"}
    schemas = esquema["components"]["schemas"]
    assert set(schemas["TurnoCreate"]["required"]) == {
        "profesional_id",
        "paciente_id",
        "prestacion_id",
        "inicio",
    }
    assert not {"fin", "estado", "codigo_publico", "tenant_id"} & set(
        schemas["TurnoCreate"]["properties"]
    )
    assert set(schemas["TurnoEstado"]["properties"]) == {"estado", "motivo_cancelacion"}
    assert set(schemas["TurnoReprogramar"]["properties"]) == {"nuevo_inicio"}
    for nombre in (
        "TurnoCreate",
        "TurnoPublic",
        "TurnoEstado",
        "TurnoReprogramar",
        "CancelarTurno",
        "AccionVacia",
    ):
        assert schemas[nombre]["additionalProperties"] is False
    assert not {"observaciones", "telefono", "paciente"} & set(schemas["TurnoPublic"]["properties"])
