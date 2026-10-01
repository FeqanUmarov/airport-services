"""Archive legacy RESA runway areas.

Revision ID: c4f1a8d72b90
Revises: ab39f621d8ce
"""

from alembic import op
import sqlalchemy as sa


revision: str = "c4f1a8d72b90"
down_revision: str | None = "ab39f621d8ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('''
        UPDATE "TBL_RUNWAY_AREAS"
        SET "STATUS_ID" = (
            SELECT "STATUS_ID" FROM "DIC_STATUS"
            WHERE lower("ENG_NAME") = 'archived'
        )
        WHERE "AREA_TYPE_ID" = (
            SELECT "AREA_TYPE_ID" FROM "DIC_RUNWAY_AREA_TYPES"
            WHERE upper("CODE") = 'RESA'
        )
    '''))
    op.execute(sa.text('''
        UPDATE "DIC_RUNWAY_AREA_TYPES"
        SET "STATUS_ID" = (
            SELECT "STATUS_ID" FROM "DIC_STATUS"
            WHERE lower("ENG_NAME") = 'archived'
        )
        WHERE upper("CODE") = 'RESA'
    '''))


def downgrade() -> None:
    op.execute(sa.text('''
        UPDATE "DIC_RUNWAY_AREA_TYPES"
        SET "STATUS_ID" = (
            SELECT "STATUS_ID" FROM "DIC_STATUS"
            WHERE lower("ENG_NAME") = 'active'
        )
        WHERE upper("CODE") = 'RESA'
    '''))
