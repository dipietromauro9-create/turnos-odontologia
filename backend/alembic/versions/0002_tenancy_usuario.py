"""Tenancy + usuarios: extension citext, tablas tenant/usuario, constraints e índices.

Revision ID: 0002_tenancy_usuario
Revises: 0001_baseline
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_tenancy_usuario"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "tenant",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_tenant"),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
        sa.CheckConstraint("length(trim(slug)) > 0", name="slug_no_vacio"),
    )

    op.create_table(
        "usuario",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("rol", sa.String(length=20), nullable=False),
        sa.Column(
            "es_dueno",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="fk_usuario_tenant_id_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_usuario_tenant_id_email"),
        sa.CheckConstraint(
            "rol IN ('recepcion', 'profesional')",
            name="rol",
        ),
        sa.CheckConstraint(
            "NOT es_dueno OR rol = 'profesional'",
            name="dueno_profesional",
        ),
    )
    op.create_index("ix_usuario_tenant_id_rol", "usuario", ["tenant_id", "rol"])


def downgrade() -> None:
    op.drop_index("ix_usuario_tenant_id_rol", table_name="usuario")
    op.drop_table("usuario")
    op.drop_table("tenant")
    # No eliminar citext si otro objeto de la base todavía lo usa.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE udt_name = 'citext'
            ) THEN
                DROP EXTENSION IF EXISTS citext;
            END IF;
        END
        $$;
        """
    )
