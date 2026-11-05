"""Turnos y defensa concurrente anti-solape.

Revision ID: 0006_turno
Revises: 0005_disponibilidad_bloqueo
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_turno"
down_revision = "0005_disponibilidad_bloqueo"
branch_labels = None
depends_on = None

ESTADOS = ("reservado", "confirmado", "atendido", "cancelado", "ausente")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    postgresql.ENUM(*ESTADOS, name="estado_turno").create(op.get_bind(), checkfirst=True)
    op.create_table(
        "turno",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_id", sa.Uuid(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "estado",
            postgresql.ENUM(*ESTADOS, name="estado_turno", create_type=False),
            nullable=False,
        ),
        sa.Column("codigo_publico", sa.String(12), nullable=False),
        sa.Column("es_sobreturno", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("motivo_sobreturno", sa.Text(), nullable=True),
        sa.Column("motivo_cancelacion", sa.Text(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_turno"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], name="fk_turno_tenant_id_tenant"),
        *[
            sa.ForeignKeyConstraint(
                [f"{tabla}_id"],
                [f"{tabla}.id"],
                ondelete="RESTRICT",
                name=f"fk_turno_{tabla}_id_{tabla}",
            )
            for tabla in ("profesional", "paciente", "prestacion")
        ],
        sa.CheckConstraint("fin > inicio", name="rango_valido"),
        sa.CheckConstraint("length(codigo_publico) = 12", name="codigo_valido"),
        sa.CheckConstraint(
            "(es_sobreturno AND motivo_sobreturno IS NOT NULL AND length(trim(motivo_sobreturno)) > 0) OR (NOT es_sobreturno AND motivo_sobreturno IS NULL)",
            name="sobreturno_coherente",
        ),
        sa.UniqueConstraint("codigo_publico", name="uq_turno_codigo_publico"),
        postgresql.ExcludeConstraint(
            ("tenant_id", "="),
            ("profesional_id", "="),
            (
                sa.func.tstzrange(sa.column("inicio"), sa.column("fin"), sa.literal_column("'[)'")),
                "&&",
            ),
            where=sa.text("estado <> 'cancelado'"),
            name="ex_turno_profesional_no_solape",
            using="gist",
        ),
    )
    op.create_index(
        "ix_turno_tenant_profesional_inicio", "turno", ["tenant_id", "profesional_id", "inicio"]
    )
    op.create_index("ix_turno_tenant_estado_inicio", "turno", ["tenant_id", "estado", "inicio"])


def downgrade() -> None:
    op.drop_table("turno")
    postgresql.ENUM(*ESTADOS, name="estado_turno").drop(op.get_bind(), checkfirst=True)
