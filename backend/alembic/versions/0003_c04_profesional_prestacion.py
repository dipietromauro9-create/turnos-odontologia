"""Catálogo de agenda: tablas profesional y prestacion, FKs, checks e índices.

Revision ID: 0003_c04_profesional_prestacion
Revises: 0002_tenancy_usuario
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_c04_profesional_prestacion"
down_revision = "0002_tenancy_usuario"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profesional",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("matricula", sa.String(length=50), nullable=True),
        sa.Column("especialidad", sa.String(length=120), nullable=True),
        sa.Column(
            "activo",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profesional"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="fk_profesional_tenant_id_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name="fk_profesional_usuario_id_usuario",
        ),
        sa.UniqueConstraint("usuario_id", name="uq_profesional_usuario_id"),
    )
    op.create_index("ix_profesional_tenant_id_activo", "profesional", ["tenant_id", "activo"])

    op.create_table(
        "prestacion",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("precio_ref", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "activa",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prestacion"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="fk_prestacion_tenant_id_tenant",
        ),
        sa.CheckConstraint(
            "duracion_min > 0 AND duracion_min % 5 = 0",
            name="duracion_multiplo_5",
        ),
        sa.CheckConstraint(
            "precio_ref IS NULL OR precio_ref >= 0",
            name="precio_no_negativo",
        ),
    )
    op.create_index("ix_prestacion_tenant_id_activa", "prestacion", ["tenant_id", "activa"])


def downgrade() -> None:
    op.drop_index("ix_prestacion_tenant_id_activa", table_name="prestacion")
    op.drop_table("prestacion")
    op.drop_index("ix_profesional_tenant_id_activo", table_name="profesional")
    op.drop_table("profesional")
