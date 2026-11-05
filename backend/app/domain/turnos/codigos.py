"""Códigos opacos de 12 caracteres, con 72 bits de entropía."""

import secrets


def generar_codigo() -> str:
    return secrets.token_urlsafe(9)
