"""seed_auth_reference_data

Revision ID: d8387c10fe9a
Revises: 9b68c1c13892
Create Date: 2026-09-19 10:01:40.469646
"""

from collections.abc import Sequence

from alembic import op
import geoalchemy2
import sqlalchemy as sa


revision: str = 'd8387c10fe9a'
down_revision: str | None = '9b68c1c13892'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            '''
            INSERT INTO "DIC_STATUS" ("AZE_NAME", "ENG_NAME", "DESCRIPTION")
            VALUES
                ('Aktiv', 'Active', 'Qeyd aktivdir və istifadə edilə bilər.'),
                ('Deaktiv', 'Inactive', 'Qeyd müvəqqəti olaraq deaktivdir.'),
                ('Arxiv', 'Archived', 'Qeyd arxivləşdirilib.')
            ON CONFLICT ("ENG_NAME") DO NOTHING
            '''
        )
    )
    op.execute(
        sa.text(
            '''
            INSERT INTO "DIC_ROLES" ("CODE", "AZE_NAME", "ENG_NAME", "STATUS_ID")
            SELECT seed."CODE", seed."AZE_NAME", seed."ENG_NAME", status."STATUS_ID"
            FROM (
                VALUES
                    ('ADMIN', 'Administrator', 'Administrator'),
                    ('EDITOR', 'Redaktor', 'Editor'),
                    ('VIEWER', 'İzləyici', 'Viewer')
            ) AS seed("CODE", "AZE_NAME", "ENG_NAME")
            CROSS JOIN "DIC_STATUS" AS status
            WHERE status."ENG_NAME" = 'Active'
            ON CONFLICT ("CODE") DO NOTHING
            '''
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            '''
            DELETE FROM "DIC_ROLES"
            WHERE "CODE" IN ('ADMIN', 'EDITOR', 'VIEWER')
            '''
        )
    )
    op.execute(
        sa.text(
            '''
            DELETE FROM "DIC_STATUS"
            WHERE "ENG_NAME" IN ('Active', 'Inactive', 'Archived')
            '''
        )
    )
