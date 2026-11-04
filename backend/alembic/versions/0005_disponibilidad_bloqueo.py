"""Plantilla semanal y cierres puntuales de agenda.

C-06 es el ordinal de dominio 004 de CHANGES.md; la revisión literal es 0005.
Revision ID: 0005_disponibilidad_bloqueo
Revises: 0004_paciente
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_disponibilidad_bloqueo"
down_revision = "0004_paciente"
branch_labels = None
depends_on = None


def _identidad_y_auditoria() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "disponibilidad",
        *_identidad_y_auditoria(),
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("hora_desde", sa.Time(timezone=False), nullable=False),
        sa.Column("hora_hasta", sa.Time(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_disponibilidad"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_disponibilidad_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesional.id"],
            ondelete="RESTRICT",
            name="fk_disponibilidad_profesional_id_profesional",
        ),
        sa.CheckConstraint("dia_semana BETWEEN 0 AND 6", name="dia_semana_valido"),
        sa.CheckConstraint("hora_hasta > hora_desde", name="rango_valido"),
        sa.UniqueConstraint(
            "tenant_id",
            "profesional_id",
            "dia_semana",
            "hora_desde",
            "hora_hasta",
            name="uq_disponibilidad_tenant_profesional_dia_rango",
        ),
    )
    op.create_index(
        "ix_disponibilidad_tenant_profesional_dia",
        "disponibilidad",
        ["tenant_id", "profesional_id", "dia_semana"],
    )
    op.create_table(
        "bloqueo",
        *_identidad_y_auditoria(),
        sa.Column("profesional_id", sa.Uuid(), nullable=True),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_bloqueo"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], name="fk_bloqueo_tenant_id_tenant"),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesional.id"],
            ondelete="RESTRICT",
            name="fk_bloqueo_profesional_id_profesional",
        ),
        sa.CheckConstraint("hasta > desde", name="rango_valido"),
        sa.CheckConstraint("length(trim(motivo)) > 0", name="motivo_no_vacio"),
    )
    op.create_index(
        "ix_bloqueo_tenant_profesional_desde", "bloqueo", ["tenant_id", "profesional_id", "desde"]
    )


def downgrade() -> None:
    op.drop_index("ix_bloqueo_tenant_profesional_desde", table_name="bloqueo")
    op.drop_table("bloqueo")
    op.drop_index("ix_disponibilidad_tenant_profesional_dia", table_name="disponibilidad")
    op.drop_table("disponibilidad")
