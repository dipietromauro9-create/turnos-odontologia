"""Detector de frontera pública RN-PA-02: ninguna ruta pública expone pacientes.

No hace red: inspecciona rutas FastAPI, las allowlists de exención de JWT y el
esquema OpenAPI generado en memoria.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.domain.auth import middleware as auth_middleware

PREFIJO_PACIENTES = "/pacientes"

SCHEMAS_SENSIBLES = frozenset(
    {
        "PacienteOut",
        "PacienteCreadoOut",
        "PacienteIdentidadMinima",
        "PacienteResumen",
        "AdvertenciaDuplicado",
    }
)


def _coincide_con_pacientes(ruta: str) -> bool:
    return ruta == PREFIJO_PACIENTES or ruta.startswith(f"{PREFIJO_PACIENTES}/")


def _es_publica(ruta: str, rutas: Iterable[str], prefijos: Iterable[str]) -> bool:
    if ruta in rutas:
        return True
    return ruta == "/turnero" or any(ruta.startswith(prefijo) for prefijo in prefijos)


def _schemas_en_rutas_publicas(
    app: FastAPI, rutas: Iterable[str], prefijos: Iterable[str]
) -> set[str]:
    """`$ref` de respuesta en paths públicos del OpenAPI (la auth va por middleware)."""
    esquema = app.openapi()
    sensibles: set[str] = set()
    for ruta, operacion in (esquema.get("paths") or {}).items():
        if not _es_publica(ruta, rutas, prefijos):
            continue
        for detalle in operacion.values():
            if not isinstance(detalle, dict):
                continue
            for respuesta in (detalle.get("responses") or {}).values():
                contenido = respuesta.get("content") or {}
                for media in contenido.values():
                    nombre = (media.get("schema") or {}).get("$ref", "").rsplit("/", 1)[-1]
                    if nombre:
                        sensibles.add(nombre)
    return sensibles


def rutas_publicas_que_exponen_pacientes(
    app: FastAPI,
    *,
    rutas_publicas: Iterable[str] | None = None,
    prefijos_publicos: Iterable[str] | None = None,
) -> list[str]:
    """Rutas públicas que tocan `/pacientes` o serializan schemas de la ficha.

    Considera exposición si el path es público (por allowlist o prefijo) y
    coincide con `/pacientes`, o si una ruta pública devuelve un schema de la
    ficha (por anotación de retorno o por el OpenAPI generado).
    """
    if rutas_publicas is None or prefijos_publicos is None:
        from tests import test_architecture as guard_arquitectura

        if rutas_publicas is None:
            rutas_publicas = set(auth_middleware.RUTAS_PUBLICAS) | set(
                guard_arquitectura.RUTAS_PUBLICAS
            )
        if prefijos_publicos is None:
            prefijos_publicos = (
                *auth_middleware.PREFIJOS_PUBLICOS,
                *guard_arquitectura.PREFIJOS_PUBLICOS,
            )
    rutas = frozenset(rutas_publicas)
    prefijos = tuple(prefijos_publicos)

    expuestas: set[str] = {ruta for ruta in rutas if _coincide_con_pacientes(ruta)} | {
        prefijo for prefijo in prefijos if _coincide_con_pacientes(prefijo)
    }

    for route in app.routes:
        if not isinstance(route, APIRoute) or not _es_publica(route.path, rutas, prefijos):
            continue
        modelo = getattr(route, "response_model", None)
        nombre = getattr(modelo, "__name__", "")
        if _coincide_con_pacientes(route.path) or nombre in SCHEMAS_SENSIBLES:
            expuestas.add(route.path)

    for nombre in _schemas_en_rutas_publicas(app, rutas, prefijos):
        if nombre in SCHEMAS_SENSIBLES:
            expuestas.add(f"openapi:{nombre}")

    return sorted(expuestas)


__all__ = [
    "PREFIJO_PACIENTES",
    "SCHEMAS_SENSIBLES",
    "rutas_publicas_que_exponen_pacientes",
]
