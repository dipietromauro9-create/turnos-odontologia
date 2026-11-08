"""Recordatorios manuales por WhatsApp (C-11).

Revision ID: 0007_recordatorio
Revises: 0006_turno
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_recordatorio"
down_revision = "0006_turno"
branch_labels = None
depends_on = None

CANALES = ("whatsapp_manual",)
ESTADOS = ("pendiente", "enviado", "fallido")


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*CANALES, name="canal_recordatorio").create(bind, checkfirst=True)
    postgresql.ENUM(*ESTADOS, name="estado_recordatorio").create(bind, checkfirst=True)
    op.create_table(
        "recordatorio",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("turno_id", sa.Uuid(), nullable=False),
        sa.Column(
            "canal",
            postgresql.ENUM(*CANALES, name="canal_recordatorio", create_type=False),
            nullable=False,
        ),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "estado",
            postgresql.ENUM(*ESTADOS, name="estado_recordatorio", create_type=False),
            nullable=False,
        ),
        sa.Column("enviado_por", sa.Uuid(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recordatorio"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_recordatorio_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["turno_id"],
            ["turno.id"],
            ondelete="CASCADE",
            name="fk_recordatorio_turno_id_turno",
        ),
        sa.ForeignKeyConstraint(
            ["enviado_por"],
            ["usuario.id"],
            ondelete="SET NULL",
            name="fk_recordatorio_enviado_por_usuario",
        ),
        sa.UniqueConstraint("tenant_id", "turno_id", name="uq_recordatorio_turno"),
        sa.CheckConstraint(
            "estado <> 'enviado' OR enviado_por IS NOT NULL",
            name="enviado_por_coherente",
        ),
    )
    op.create_index("ix_recordatorio_tenant_estado", "recordatorio", ["tenant_id", "estado"])


def downgrade() -> None:
    op.drop_index("ix_recordatorio_tenant_estado", table_name="recordatorio")
    op.drop_table("recordatorio")
    bind = op.get_bind()
    postgresql.ENUM(*ESTADOS, name="estado_recordatorio").drop(bind, checkfirst=True)
    postgresql.ENUM(*CANALES, name="canal_recordatorio").drop(bind, checkfirst=True)
