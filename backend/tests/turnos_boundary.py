"""Inspección estática R4 y esquema de rutas públicas, sin red ni DB."""

import ast
from pathlib import Path

from fastapi import FastAPI

from app.domain.auth.middleware import PREFIJOS_PUBLICOS, RUTAS_PUBLICAS

CAMPOS_PROTEGIDOS = frozenset(
    {
        "estado",
        "inicio",
        "fin",
        "codigo_publico",
        "profesional_id",
        "paciente_id",
        "prestacion_id",
        "es_sobreturno",
    }
)


def escrituras_fuera_del_servicio(raiz: Path) -> list[str]:
    infracciones = []
    for archivo in sorted(raiz.rglob("*.py")):
        relativo = archivo.relative_to(raiz).as_posix()
        if relativo == "domain/turnos/service.py":
            continue
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        aliases = {
            alias.asname or alias.name
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.ImportFrom)
            for alias in nodo.names
            if alias.name == "Turno"
        }
        constructores = aliases | {"Turno"}
        ilegal = False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                funcion = nodo.func
                if isinstance(funcion, ast.Name) and funcion.id in constructores:
                    ilegal = True
                if (
                    isinstance(funcion, ast.Name)
                    and funcion.id in {"insert", "update", "delete"}
                    and nodo.args
                    and isinstance(nodo.args[0], ast.Name)
                    and nodo.args[0].id in constructores
                ):
                    ilegal = True
            if aliases and isinstance(nodo, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
                if any(
                    isinstance(d, ast.Attribute) and d.attr in CAMPOS_PROTEGIDOS for d in destinos
                ):
                    ilegal = True
        if ilegal:
            infracciones.append(relativo)
    return infracciones


def rutas_publicas_que_exponen_turnos(app: FastAPI) -> list[str]:
    esquema = app.openapi()
    componentes = esquema.get("components", {}).get("schemas", {})

    def sensible(nodo: object, vistos: frozenset[str] = frozenset()) -> bool:
        if isinstance(nodo, dict):
            ref = nodo.get("$ref", "")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                nombre = ref.rsplit("/", 1)[-1]
                if nombre == "TurnoPublic":
                    return True
                if nombre not in vistos and sensible(
                    componentes.get(nombre, {}), vistos | {nombre}
                ):
                    return True
            return any(sensible(v, vistos) for v in nodo.values())
        if isinstance(nodo, list):
            return any(sensible(v, vistos) for v in nodo)
        return False

    return sorted(
        path
        for path, contenido in esquema.get("paths", {}).items()
        if (path in RUTAS_PUBLICAS or path == "/turnero" or path.startswith(PREFIJOS_PUBLICOS))
        and (path == "/turnos" or path.startswith("/turnos/") or sensible(contenido))
    )
