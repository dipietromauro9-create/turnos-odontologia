"""Primitivas de seguridad: Argon2id, emisión de JWT y validación de claims."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import (
    TokenError,
    crear_token,
    decodificar_token,
    hash_password,
    verificar_password_ficticia,
    verify_password,
)

SECRET_KEY = "t" * 40
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USUARIO_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
REQUIRED_CLAIMS: Sequence[str] = (
    "sub",
    "tenant_id",
    "roles",
    "email",
    "jti",
    "type",
    "iat",
    "exp",
)


def _emitir(
    tipo: str = "access",
    *,
    sub: uuid.UUID = USUARIO_ID,
    tenant_id: uuid.UUID = TENANT_ID,
    email: str = "dueno@demo",
    roles: Sequence[str] = ("profesional",),
    ahora: datetime | None = None,
) -> str:
    return crear_token(
        sub=sub,
        tenant_id=tenant_id,
        email=email,
        roles=roles,
        tipo=tipo,
        ahora=ahora,
    )


def test_hash_de_la_misma_password_es_distinto_por_salt() -> None:
    primero = hash_password("clave-ficticia-2026")
    segundo = hash_password("clave-ficticia-2026")

    assert primero != segundo
    assert verify_password("clave-ficticia-2026", primero) is True
    assert verify_password("clave-ficticia-2026", segundo) is True


def test_verify_rechaza_una_password_distinta() -> None:
    hasheada = hash_password("clave-ficticia-2026")

    assert verify_password("clave-incorrecta", hasheada) is False


def test_access_emite_los_claims_requeridos_y_vence_en_15_minutos(app_env: None) -> None:
    token = _emitir("access")

    payload = decodificar_token(token, tipo_esperado="access")

    assert set(REQUIRED_CLAIMS) <= payload.keys()
    assert payload["sub"] == str(USUARIO_ID)
    assert payload["tenant_id"] == str(TENANT_ID)
    assert payload["email"] == "dueno@demo"
    assert payload["roles"] == ["profesional"]
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_refresh_emite_los_claims_requeridos_y_vence_en_7_dias(app_env: None) -> None:
    token = _emitir("refresh")

    payload = decodificar_token(token, tipo_esperado="refresh")

    assert set(REQUIRED_CLAIMS) <= payload.keys()
    assert payload["type"] == "refresh"
    assert payload["exp"] - payload["iat"] == 7 * 24 * 60 * 60


def test_decodificar_rechaza_una_firma_invalida(app_env: None) -> None:
    payload = {
        "sub": str(USUARIO_ID),
        "tenant_id": str(TENANT_ID),
        "roles": ["profesional"],
        "email": "dueno@demo",
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
    }
    ajeno = jwt.encode(payload, "x" * 40, algorithm="HS256")

    with pytest.raises(TokenError) as excinfo:
        decodificar_token(ajeno, tipo_esperado="access")

    assert excinfo.value.motivo == "token_invalido"


def test_decodificar_rechaza_un_token_expirado(app_env: None) -> None:
    token = _emitir("access", ahora=datetime.now(UTC) - timedelta(minutes=16))

    with pytest.raises(TokenError) as excinfo:
        decodificar_token(token, tipo_esperado="access")

    assert excinfo.value.motivo == "token_expirado"


def test_decodificar_rechaza_un_tipo_inesperado(app_env: None) -> None:
    token = _emitir("refresh")

    with pytest.raises(TokenError) as excinfo:
        decodificar_token(token, tipo_esperado="access")

    assert excinfo.value.motivo == "token_invalido"


def test_decodificar_rechaza_un_token_sin_claims_requeridos(app_env: None) -> None:
    incompleto = jwt.encode(
        {
            "sub": str(USUARIO_ID),
            "tenant_id": str(TENANT_ID),
            "roles": ["profesional"],
            "email": "dueno@demo",
            "type": "access",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    with pytest.raises(TokenError) as excinfo:
        decodificar_token(incompleto, tipo_esperado="access")

    assert excinfo.value.motivo == "token_invalido"


def _base64url(contenido: dict[str, object]) -> str:
    crudo = json.dumps(contenido, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode()


def _token_alg_none(ahora: datetime) -> str:
    header = _base64url({"alg": "none", "typ": "JWT"})
    payload = _base64url(
        {
            "sub": str(USUARIO_ID),
            "tenant_id": str(TENANT_ID),
            "roles": ["profesional"],
            "email": "dueno@demo",
            "jti": str(uuid.uuid4()),
            "type": "access",
            "iat": int(ahora.timestamp()),
            "exp": int((ahora + timedelta(minutes=15)).timestamp()),
        }
    )
    return f"{header}.{payload}."


def test_decodificar_rechaza_alg_none(app_env: None) -> None:
    firmado = _token_alg_none(datetime.now(UTC))

    with pytest.raises(TokenError) as excinfo:
        decodificar_token(firmado, tipo_esperado="access")

    assert excinfo.value.motivo == "token_invalido"


def test_dos_tokens_en_el_mismo_segundo_tienen_jti_distinto(app_env: None) -> None:
    ahora = datetime.now(UTC).replace(microsecond=0)

    primero = decodificar_token(_emitir("access", ahora=ahora), tipo_esperado="access")
    segundo = decodificar_token(_emitir("access", ahora=ahora), tipo_esperado="access")

    assert primero["jti"] != segundo["jti"]
    assert primero["iat"] == segundo["iat"]


def test_motivo_distingue_expirado_de_firma_invalida(app_env: None) -> None:
    expirado = _emitir("access", ahora=datetime.now(UTC) - timedelta(minutes=16))
    firma_ajena = jwt.encode(
        {
            "sub": str(USUARIO_ID),
            "tenant_id": str(TENANT_ID),
            "roles": ["profesional"],
            "email": "dueno@demo",
            "jti": str(uuid.uuid4()),
            "type": "access",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp()),
        },
        "x" * 40,
        algorithm="HS256",
    )

    with pytest.raises(TokenError) as por_expiracion:
        decodificar_token(expirado, tipo_esperado="access")
    with pytest.raises(TokenError) as por_firma:
        decodificar_token(firma_ajena, tipo_esperado="access")

    assert por_expiracion.value.motivo == "token_expirado"
    assert por_firma.value.motivo == "token_invalido"


def test_verificar_password_ficticia_no_revela_ni_falla() -> None:
    assert verificar_password_ficticia("cualquier-clave") is None
