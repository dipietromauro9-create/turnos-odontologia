"""Línea base vacía (sin tablas de dominio todavía — C-02 agrega tenant/usuario).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
