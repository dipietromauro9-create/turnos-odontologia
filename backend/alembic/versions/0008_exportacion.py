"""Exportaciones CSV asíncronas (C-12).

Revision ID: 0008_exportacion
Revises: 0007_recordatorio
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_exportacion"
down_revision = "0007_recordatorio"
branch_labels = None
depends_on = None

TIPOS = ("turnos", "pacientes")
ESTADOS = ("pendiente", "procesando", "listo", "fallido")


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*TIPOS, name="tipo_exportacion").create(bind, checkfirst=True)
    postgresql.ENUM(*ESTADOS, name="estado_exportacion").create(bind, checkfirst=True)
    op.create_table(
        "exportacion",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tipo",
            postgresql.ENUM(*TIPOS, name="tipo_exportacion", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "estado",
            postgresql.ENUM(*ESTADOS, name="estado_exportacion", create_type=False),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contenido", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exportacion"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_exportacion_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuario.id"],
            ondelete="SET NULL",
            name="fk_exportacion_creado_por_usuario",
        ),
    )
    op.create_index("ix_exportacion_tenant_estado", "exportacion", ["tenant_id", "estado"])
    op.create_index("ix_exportacion_tenant_creado_en", "exportacion", ["tenant_id", "creado_en"])


def downgrade() -> None:
    op.drop_index("ix_exportacion_tenant_creado_en", table_name="exportacion")
    op.drop_index("ix_exportacion_tenant_estado", table_name="exportacion")
    op.drop_table("exportacion")
    bind = op.get_bind()
    postgresql.ENUM(*ESTADOS, name="estado_exportacion").drop(bind, checkfirst=True)
    postgresql.ENUM(*TIPOS, name="tipo_exportacion").drop(bind, checkfirst=True)
