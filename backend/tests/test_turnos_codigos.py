"""El código de gestión utiliza 72 bits de aleatoriedad criptográfica."""

import re

import pytest

from app.domain.turnos.codigos import generar_codigo


def test_generar_codigo_pide_nueve_bytes_a_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[int] = []

    def fuente(nbytes: int) -> str:
        pedidos.append(nbytes)
        return "abcdefgh_123"

    monkeypatch.setattr("app.domain.turnos.codigos.secrets.token_urlsafe", fuente)
    assert generar_codigo() == "abcdefgh_123"
    assert pedidos == [9]


def test_codigos_reales_tienen_formato_y_no_se_reutilizan() -> None:
    codigos = [generar_codigo() for _ in range(100)]
    assert len(set(codigos)) == 100
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{12}", codigo) for codigo in codigos)
