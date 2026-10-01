"""add_runway_declared_distances

Revision ID: 5f32bd24a7c1
Revises: 96d0124d5c29
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "5f32bd24a7c1"
down_revision: str | None = "96d0124d5c29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "TBL_RUNWAY_DECLARED_DISTANCES",
        sa.Column(
            "DECLARED_DISTANCE_ID",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("RUN_DIR_ID", sa.BigInteger(), nullable=False),
        sa.Column("TORA_M", sa.Numeric(12, 3), nullable=False),
        sa.Column("TODA_M", sa.Numeric(12, 3), nullable=False),
        sa.Column("ASDA_M", sa.Numeric(12, 3), nullable=False),
        sa.Column("LDA_M", sa.Numeric(12, 3), nullable=False),
        sa.Column("STATUS_ID", sa.Integer(), nullable=False),
        sa.Column(
            "CREATED_DATE",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "LAST_EDITED_DATE",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint('"TORA_M" > 0', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_tora_positive")),
        sa.CheckConstraint('"TODA_M" > 0', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_toda_positive")),
        sa.CheckConstraint('"ASDA_M" > 0', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_asda_positive")),
        sa.CheckConstraint('"LDA_M" > 0', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_lda_positive")),
        sa.CheckConstraint('"TODA_M" >= "TORA_M"', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_toda_gte_tora")),
        sa.CheckConstraint('"ASDA_M" >= "TORA_M"', name=op.f("ck_TBL_RUNWAY_DECLARED_DISTANCES_declared_distance_asda_gte_tora")),
        sa.ForeignKeyConstraint(
            ["RUN_DIR_ID"],
            ["TBL_RUNWAY_DIRECTIONS.RUN_DIR_ID"],
            name=op.f("fk_TBL_RUNWAY_DECLARED_DISTANCES_RUN_DIR_ID_TBL_RUNWAY_DIRECTIONS"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["STATUS_ID"],
            ["DIC_STATUS.STATUS_ID"],
            name=op.f("fk_TBL_RUNWAY_DECLARED_DISTANCES_STATUS_ID_DIC_STATUS"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "DECLARED_DISTANCE_ID",
            name=op.f("pk_TBL_RUNWAY_DECLARED_DISTANCES"),
        ),
        sa.UniqueConstraint(
            "RUN_DIR_ID",
            name=op.f("uq_TBL_RUNWAY_DECLARED_DISTANCES_RUN_DIR_ID"),
        ),
    )
    op.create_index(
        "ix_TBL_RUNWAY_DECLARED_DISTANCES_STATUS_ID",
        "TBL_RUNWAY_DECLARED_DISTANCES",
        ["STATUS_ID"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_TBL_RUNWAY_DECLARED_DISTANCES_STATUS_ID",
        table_name="TBL_RUNWAY_DECLARED_DISTANCES",
    )
    op.drop_table("TBL_RUNWAY_DECLARED_DISTANCES")
