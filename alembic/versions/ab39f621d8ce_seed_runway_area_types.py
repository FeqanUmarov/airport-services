"""Seed runway area type dictionary.

Revision ID: ab39f621d8ce
Revises: e2c47a9186bd
Create Date: 2026-09-23
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "ab39f621d8ce"
down_revision: str | None = "e2c47a9186bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AREA_TYPES = (
    ("CWY", "Maneəsiz zona", "Clearway", "Take-off run sonunda maneəsiz düzbucaqlı sahə."),
    ("SWY", "Dayanma zolağı", "Stopway", "Uçuşdan imtina zamanı təyyarənin dayandırılması üçün sahə."),
    ("RESA", "Runway sonu təhlükəsizlik sahəsi", "Runway end safety area", "Runway sonundan çıxma riskini azaltmaq üçün təhlükəsizlik sahəsi."),
)

def upgrade() -> None:
    connection = op.get_bind()
    status_id = connection.execute(sa.text("SELECT \"STATUS_ID\" FROM \"DIC_STATUS\" WHERE lower(\"ENG_NAME\")='active' ORDER BY \"STATUS_ID\" LIMIT 1")).scalar_one()
    statement = sa.text('INSERT INTO "DIC_RUNWAY_AREA_TYPES" ("CODE","AZE_NAME","ENG_NAME","DESCRIPTION","STATUS_ID") VALUES (:code,:aze,:eng,:description,:status_id) ON CONFLICT ("CODE") DO NOTHING')
    connection.execute(statement,[{"code":code,"aze":aze,"eng":eng,"description":description,"status_id":status_id} for code,aze,eng,description in AREA_TYPES])

def downgrade() -> None:
    op.execute(sa.text('DELETE FROM "DIC_RUNWAY_AREA_TYPES" AS type WHERE type."CODE" IN (\'CWY\',\'SWY\',\'RESA\') AND NOT EXISTS (SELECT 1 FROM "TBL_RUNWAY_AREAS" AS area WHERE area."AREA_TYPE_ID"=type."AREA_TYPE_ID")'))
