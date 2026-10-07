"""Excepción base de dominio + handler (RN-GL-01: sobre {code, message, details?})."""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

_CODE_RE = re.compile(r"^RN-[A-Z]{2}-\d{2}$")


class ErrorEnvelope(BaseModel):
    """Sobre de error de dominio. R1: rechaza campos no declarados."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^RN-[A-Z]{2}-\d{2}$")
    message: str = Field(min_length=1)
    details: dict[str, Any] | None = None


class DomainError(Exception):
    """Fallo de negocio conocido → siempre 4xx con código RN-XX-NN, nunca 500."""

    def __init__(
        self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None
    ) -> None:
        if not _CODE_RE.match(code):
            msg = f"code debe tener formato RN-XX-NN, recibido: {code}"
            raise ValueError(msg)
        if not 400 <= status_code < 500:
            msg = f"DomainError requiere status 4xx, recibido: {status_code}"
            raise ValueError(msg)
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    envelope = ErrorEnvelope(code=exc.code, message=exc.message, details=exc.details)
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(exclude_none=True))


def register_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
