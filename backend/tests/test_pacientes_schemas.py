"""Contratos Pydantic de paciente: normalización de teléfono y validaciones (R1)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.domain.pacientes.schemas import (
    PacienteCreate,
    PacienteOut,
    PacienteUpdate,
)
from app.domain.pacientes.service import normalizar_telefono

HOY = date.today()


def _datos_validos(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {"nombre": "Paciente Ficticio", "telefono": "11 4555-0001"}
    datos.update(cambios)
    return datos


@pytest.mark.parametrize(
    "schema",
    [PacienteCreate, PacienteUpdate, PacienteOut],
)
def test_los_schemas_rechazan_campos_extra(schema: type) -> None:
    campos = {
        "id": "00000000-0000-0000-0000-000000000001",
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "nombre": "Paciente Ficticio",
        "telefono": "1145550001",
        "documento": None,
        "fecha_nac": None,
        "observaciones": None,
        "creado_en": datetime.now(UTC),
        "actualizado_en": datetime.now(UTC),
        "campo_intruso": "no permitido",
    }
    with pytest.raises(ValidationError):
        schema(**campos)


def test_normaliza_telefono_con_formato_humano() -> None:
    assert normalizar_telefono("+54 9 11 4555-0001") == "5491145550001"


@pytest.mark.parametrize("telefono", ["12345", "1" * 16, "123-45"])
def test_telefono_con_menos_de_seis_o_mas_de_quince_digitos_se_rechaza(
    telefono: str,
) -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**_datos_validos(telefono=telefono))


@pytest.mark.parametrize("digitos", [6, 15])
def test_los_limites_de_digitos_del_telefono_son_inclusivos(digitos: int) -> None:
    telefono = "1" * digitos

    creado = PacienteCreate(**_datos_validos(telefono=telefono))

    assert creado.telefono == telefono


@pytest.mark.parametrize(
    "fecha",
    [HOY + timedelta(days=1), date(1899, 12, 31)],
)
def test_fecha_nac_futura_o_anterior_a_1900_se_rechaza(fecha: date) -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**_datos_validos(fecha_nac=fecha))


def test_update_acepta_body_vacio_y_todos_sus_campos_son_opcionales() -> None:
    update = PacienteUpdate()

    assert update.model_dump(exclude_unset=True) == {}
    assert PacienteUpdate.model_fields["nombre"].is_required() is False
    assert PacienteUpdate.model_fields["telefono"].is_required() is False
    assert PacienteUpdate.model_fields["documento"].is_required() is False
    assert PacienteUpdate.model_fields["fecha_nac"].is_required() is False
    assert PacienteUpdate.model_fields["observaciones"].is_required() is False


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("11 4555-0001", "1145550001"),
        ("(011) 4555-0001", "01145550001"),
        ("01145550001", "01145550001"),
    ],
)
def test_telefonos_con_distintos_formatos_normalizan_a_digitos(entrada: str, esperado: str) -> None:
    assert normalizar_telefono(entrada) == esperado


def test_telefono_compuesto_solo_por_simbolos_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**_datos_validos(telefono="--- ( ) +++"))


def test_paciente_out_expone_timestamps_con_zona_y_no_el_creador() -> None:
    creado = datetime.now(UTC).replace(microsecond=0)
    salida = PacienteOut(
        id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        nombre="Paciente Ficticio",
        telefono="1145550001",
        documento=None,
        fecha_nac=None,
        observaciones=None,
        creado_en=creado,
        actualizado_en=creado,
    )

    volcado = salida.model_dump(mode="json")
    assert volcado["creado_en"].endswith(("+00:00", "Z"))
    assert volcado["actualizado_en"].endswith(("+00:00", "Z"))
    assert "creado_por_usuario_id" not in PacienteOut.model_fields


def test_paciente_out_rechaza_un_timestamp_sin_zona() -> None:
    with pytest.raises(ValidationError):
        PacienteOut(
            id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            nombre="Paciente Ficticio",
            telefono="1145550001",
            documento=None,
            fecha_nac=None,
            observaciones=None,
            creado_en=datetime(2026, 1, 1, 9, 0),
            actualizado_en=datetime(2026, 1, 1, 9, 0),
        )


def test_paciente_create_rechaza_un_campo_desconocido() -> None:
    with pytest.raises(ValidationError) as exc:
        PacienteCreate(**_datos_validos(rol="profesional"))

    assert "rol" in str(exc.value)
