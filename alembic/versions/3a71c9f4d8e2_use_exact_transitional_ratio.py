"""use the exact 1:7 Transitional slope

Revision ID: 3a71c9f4d8e2
Revises: c4f1a8d72b90
Create Date: 2026-10-01
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3a71c9f4d8e2"
down_revision: str | None = "c4f1a8d72b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_slope(value: float, description: str) -> None:
    op.execute(
        sa.text(
            '''
            UPDATE "TBL_STANDARD_OLS_PARAMETER_VALUES" value
            SET "NUMERIC_VALUE" = :value,
                "DESCRIPTION" = :description
            FROM "TBL_STANDARD_OLS_SURFACES" config
            JOIN "TBL_STANDARDS" standard
              ON standard."STANDARD_ID" = config."STANDARD_ID"
            JOIN "DIC_OLS_SURFACE_TYPES" surface_type
              ON surface_type."SURFACE_TYPE_ID" = config."SURFACE_TYPE_ID"
            , "DIC_OLS_PARAMETERS" parameter
            WHERE value."STANDARD_OLS_ID" = config."STANDARD_OLS_ID"
              AND parameter."PARAMETER_ID" = value."PARAMETER_ID"
              AND standard."CODE" = 'ICAO_ANNEX_14_V1_ZANGILAN'
              AND surface_type."CODE" = 'TRANSITIONAL'
              AND parameter."CODE" = 'SLOPE'
              AND value."SECTION_NO" = 0
            '''
        ).bindparams(value=value, description=description)
    )


def upgrade() -> None:
    _set_slope(14.285714, "Exact 1:7 slope; start elevation varies along the lower edge")


def downgrade() -> None:
    _set_slope(14.3, "Approximate 1:7 slope; start elevation varies along boundary")
