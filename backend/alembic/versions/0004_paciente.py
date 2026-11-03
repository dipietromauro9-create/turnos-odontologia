"""Paciente: tabla tenant-scoped, extensiones de búsqueda, FKs, CHECKs e índices.

Revision ID: 0004_paciente
Revises: 0003_c04_profesional_prestacion
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_paciente"
down_revision = "0003_c04_profesional_prestacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")

    op.create_table(
        "paciente",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("creado_por_usuario_id", sa.Uuid(), nullable=True),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("telefono", sa.String(length=15), nullable=False),
        sa.Column("documento", sa.String(length=50), nullable=True),
        sa.Column("fecha_nac", sa.Date(), nullable=True),
        sa.Column("observaciones", sa.String(length=2000), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_paciente"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="fk_paciente_tenant_id_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_usuario_id"],
            ["usuario.id"],
            name="fk_paciente_creado_por_usuario_id_usuario",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("length(trim(nombre)) > 0", name="nombre_no_vacio"),
        sa.CheckConstraint(
            "telefono ~ '^[0-9]{6,15}$'",
            name="telefono_digitos",
        ),
    )
    op.create_index("ix_paciente_tenant_id_telefono", "paciente", ["tenant_id", "telefono"])
    op.create_index(
        "ix_paciente_tenant_id_creado_por_usuario_id",
        "paciente",
        ["tenant_id", "creado_por_usuario_id"],
    )
    op.create_index(
        "ix_paciente_tenant_id_nombre_trgm",
        "paciente",
        ["tenant_id", sa.text("lower(nombre) gin_trgm_ops")],
        postgresql_using="gin",
        postgresql_ops={"tenant_id": "uuid_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_paciente_tenant_id_nombre_trgm", table_name="paciente")
    op.drop_index("ix_paciente_tenant_id_creado_por_usuario_id", table_name="paciente")
    op.drop_index("ix_paciente_tenant_id_telefono", table_name="paciente")
    op.drop_table("paciente")
    # No eliminar las extensiones si otro objeto de la base todavía las usa.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexdef LIKE '%gin_trgm_ops%'
            ) THEN
                DROP EXTENSION IF EXISTS pg_trgm;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexdef LIKE '% USING gin %'
            ) THEN
                DROP EXTENSION IF EXISTS btree_gin;
            END IF;
        END
        $$;
        """
    )
