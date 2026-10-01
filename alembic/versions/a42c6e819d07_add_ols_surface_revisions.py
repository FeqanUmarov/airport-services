"""add_ols_surface_revisions

Revision ID: a42c6e819d07
Revises: 5f32bd24a7c1
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op
import geoalchemy2
import sqlalchemy as sa


revision: str = "a42c6e819d07"
down_revision: str | None = "5f32bd24a7c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "TBL_OLS_SURFACE_REVISIONS",
        sa.Column("REVISION_ID", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("OLS_SURFACE_ID", sa.BigInteger(), nullable=False),
        sa.Column("REVISION_NO", sa.Integer(), nullable=False),
        sa.Column("STANDARD_OLS_ID", sa.BigInteger(), nullable=False),
        sa.Column("GENERATION_METHOD_ID", sa.Integer(), nullable=False),
        sa.Column("AIR_ID", sa.BigInteger(), nullable=False),
        sa.Column("RUN_ID", sa.BigInteger(), nullable=True),
        sa.Column("RUN_DIR_ID", sa.BigInteger(), nullable=True),
        sa.Column("AZE_NAME", sa.String(255), nullable=True),
        sa.Column("ENG_NAME", sa.String(255), nullable=True),
        sa.Column("GEOM", geoalchemy2.types.Geometry(geometry_type="GEOMETRYZ", srid=4326, dimension=3, spatial_index=False), nullable=False),
        sa.Column("STATUS_ID", sa.Integer(), nullable=False),
        sa.Column("CHANGE_TYPE", sa.String(30), nullable=False),
        sa.Column("CHANGE_NOTE", sa.String(500), nullable=True),
        sa.Column("CREATED_BY", sa.BigInteger(), nullable=True),
        sa.Column("CREATED_DATE", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["CREATED_BY"],["TBL_USERS.USER_ID"],name=op.f("fk_TBL_OLS_SURFACE_REVISIONS_CREATED_BY_TBL_USERS"),ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["OLS_SURFACE_ID"],["TBL_OLS_SURFACES.OLS_SURFACE_ID"],name=op.f("fk_TBL_OLS_SURFACE_REVISIONS_OLS_SURFACE_ID_TBL_OLS_SURFACES"),ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("REVISION_ID",name=op.f("pk_TBL_OLS_SURFACE_REVISIONS")),
        sa.UniqueConstraint("OLS_SURFACE_ID","REVISION_NO",name="uq_ols_surface_revision_no"),
    )
    op.create_index("idx_TBL_OLS_SURFACE_REVISIONS_GEOM","TBL_OLS_SURFACE_REVISIONS",["GEOM"],unique=False,postgresql_using="gist")
    op.create_index(op.f("ix_TBL_OLS_SURFACE_REVISIONS_CREATED_BY"),"TBL_OLS_SURFACE_REVISIONS",["CREATED_BY"],unique=False)
    op.create_index(op.f("ix_TBL_OLS_SURFACE_REVISIONS_OLS_SURFACE_ID"),"TBL_OLS_SURFACE_REVISIONS",["OLS_SURFACE_ID"],unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_TBL_OLS_SURFACE_REVISIONS_OLS_SURFACE_ID"),table_name="TBL_OLS_SURFACE_REVISIONS")
    op.drop_index(op.f("ix_TBL_OLS_SURFACE_REVISIONS_CREATED_BY"),table_name="TBL_OLS_SURFACE_REVISIONS")
    op.drop_index("idx_TBL_OLS_SURFACE_REVISIONS_GEOM",table_name="TBL_OLS_SURFACE_REVISIONS",postgresql_using="gist")
    op.drop_table("TBL_OLS_SURFACE_REVISIONS")
