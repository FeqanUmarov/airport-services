"""Seed verified Azerbaijan airport ICAO location indicators.

Revision ID: f4a8c9d2e731
Revises: c71e20f4a915
Create Date: 2026-09-23

The public airport operator list is used for airport names and codes. ICAO Doc
7910 remains the authoritative register of four-letter location indicators.
Laçın is intentionally omitted because the public operator page currently
duplicates Füzuli's UBBF indicator; a location indicator must be unique.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f4a8c9d2e731"
down_revision: str | None = "c71e20f4a915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOURCE_SUFFIX = " [Seed source: Azerbaijan Airports official portal, 2026-09-23]"


def upgrade() -> None:
    op.execute(
        sa.text(
            f'''\
            WITH active_status AS (
                SELECT "STATUS_ID"
                FROM "DIC_STATUS"
                WHERE lower("ENG_NAME") = 'active'
                ORDER BY "STATUS_ID"
                LIMIT 1
            ), seed("ICAO_CODE", "DESCRIPTION") AS (
                VALUES
                    ('UBBB', 'Heydər Əliyev Beynəlxalq Hava Limanı — Bakı{SOURCE_SUFFIX}'),
                    ('UBBN', 'Naxçıvan Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBG', 'Gəncə Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBQ', 'Qəbələ Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBL', 'Lənkəran Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBY', 'Zaqatala Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBF', 'Füzuli Beynəlxalq Hava Limanı{SOURCE_SUFFIX}'),
                    ('UBBZ', 'Zəngilan Beynəlxalq Hava Limanı{SOURCE_SUFFIX}')
            )
            INSERT INTO "DIC_ICAO_CODES" ("ICAO_CODE", "DESCRIPTION", "STATUS_ID")
            SELECT seed."ICAO_CODE", seed."DESCRIPTION", active_status."STATUS_ID"
            FROM seed
            CROSS JOIN active_status
            ON CONFLICT ("ICAO_CODE") DO NOTHING
            '''
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            '''
            DELETE FROM "DIC_ICAO_CODES" AS code
            WHERE code."DESCRIPTION" LIKE :source_pattern
              AND NOT EXISTS (
                  SELECT 1
                  FROM "TBL_AIRPORTS" AS airport
                  WHERE airport."ICAO_ID" = code."ICAO_ID"
              )
            '''
        ).bindparams(source_pattern=f"%{SOURCE_SUFFIX}")
    )
