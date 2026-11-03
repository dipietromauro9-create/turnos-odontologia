"""Alcance RN-AU-03 sobre pacientes: recepción/dueño ven todo, profesional sin flag lo propio."""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import DomainError
from app.db.models import Paciente, Usuario
from app.domain.auth.dependencies import AlcanceAgenda, alcance_agenda

RN_AU_03 = "RN-AU-03"


class AlcancePacientes(StrEnum):
    """Qué pacientes puede ver un usuario: todos los del consultorio o solo los suyos."""

    TODOS = "todos"
    PROPIOS = "propios"


def alcance_pacientes(usuario: Usuario) -> AlcancePacientes:
    """Reutiliza la semántica de C-03: recepción y dueño ven todo."""
    if alcance_agenda(usuario) is AlcanceAgenda.TODAS:
        return AlcancePacientes.TODOS
    return AlcancePacientes.PROPIOS


def exigir_acceso_paciente(usuario: Usuario, paciente: Paciente) -> Paciente:
    """403 `RN-AU-03` si un profesional sin flag intenta tocar un paciente ajeno.

    Diferencia con el 404 `RN-PA-02`: el 404 solo se usa cuando el paciente no
    existe en el tenant; si existe pero está fuera del alcance, se responde 403
    (y no se confirma la ficha).
    """
    if alcance_pacientes(usuario) is AlcancePacientes.TODOS:
        return paciente
    if paciente.creado_por_usuario_id != usuario.id:
        raise DomainError(
            RN_AU_03,
            "El profesional solo puede acceder a sus propios pacientes",
            status_code=403,
            details={"reason": "fuera_de_alcance"},
        )
    return paciente


__all__ = ["AlcancePacientes", "alcance_pacientes", "exigir_acceso_paciente"]
