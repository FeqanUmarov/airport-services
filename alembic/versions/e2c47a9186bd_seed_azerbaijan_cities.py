78
"""Seed Azerbaijan cities in the city dictionary.

Revision ID: e2c47a9186bd
Revises: b7d1e5a63c90
Create Date: 2026-09-23
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "e2c47a9186bd"
down_revision: str | None = "b7d1e5a63c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CITIES: tuple[tuple[str, str], ...] = (
    ("Ağcabədi", "Aghjabadi"),
    ("Ağdam", "Aghdam"),
    ("Ağdaş", "Agdash"),
    ("Ağdərə", "Aghdara"),
    ("Ağstafa", "Agstafa"),
    ("Ağsu", "Agsu"),
    ("Astara", "Astara"),
    ("Babək", "Babek"),
    ("Bakı", "Baku"),
    ("Balakən", "Balakan"),
    ("Bərdə", "Barda"),
    ("Beyləqan", "Beylagan"),
    ("Biləsuvar", "Bilasuvar"),
    ("Cəbrayıl", "Jabrayil"),
    ("Cəlilabad", "Jalilabad"),
    ("Culfa", "Julfa"),
    ("Daşkəsən", "Dashkasan"),
    ("Dəliməmmədli", "Dalimammadli"),
    ("Füzuli", "Fuzuli"),
    ("Gədəbəy", "Gadabay"),
    ("Gəncə", "Ganja"),
    ("Goranboy", "Goranboy"),
    ("Göyçay", "Goychay"),
    ("Göygöl", "Goygol"),
    ("Göytəpə", "Goytepe"),
    ("Hacıqabul", "Hajigabul"),
    ("Horadiz", "Horadiz"),
    ("İmişli", "Imishli"),
    ("İsmayıllı", "Ismayilli"),
    ("Kəlbəcər", "Kalbajar"),
    ("Kürdəmir", "Kurdamir"),
    ("Qəbələ", "Gabala"),
    ("Qax", "Gakh"),
    ("Qazax", "Gazakh"),
    ("Quba", "Guba"),
    ("Qubadlı", "Gubadli"),
    ("Qusar", "Gusar"),
    ("Laçın", "Lachin"),
    ("Lerik", "Lerik"),
    ("Lənkəran", "Lankaran"),
    ("Liman", "Liman"),
    ("Masallı", "Masalli"),
    ("Mingəçevir", "Mingachevir"),
    ("Naftalan", "Naftalan"),
    ("Naxçıvan", "Nakhchivan"),
    ("Neftçala", "Neftchala"),
    ("Oğuz", "Oghuz"),
    ("Ordubad", "Ordubad"),
    ("Qovlar", "Govlar"),
    ("Saatlı", "Saatli"),
    ("Sabirabad", "Sabirabad"),
    ("Salyan", "Salyan"),
    ("Samux", "Samukh"),
    ("Siyəzən", "Siyazan"),
    ("Sumqayıt", "Sumgait"),
    ("Şabran", "Shabran"),
    ("Şahbuz", "Shahbuz"),
    ("Şamaxı", "Shamakhi"),
    ("Şəki", "Shaki"),
    ("Şəmkir", "Shamkir"),
    ("Şərur", "Sharur"),
    ("Şirvan", "Shirvan"),
    ("Şuşa", "Shusha"),
    ("Tərtər", "Tartar"),
    ("Tovuz", "Tovuz"),
    ("Ucar", "Ujar"),
    ("Xaçmaz", "Khachmaz"),
    ("Xankəndi", "Khankendi"),
    ("Xırdalan", "Khirdalan"),
    ("Xızı", "Khizi"),
    ("Xocalı", "Khojaly"),
    ("Xocavənd", "Khojavend"),
    ("Xudat", "Khudat"),
    ("Yardımlı", "Yardimli"),
    ("Yevlax", "Yevlakh"),
    ("Zaqatala", "Zagatala"),
    ("Zəngilan", "Zangilan"),
    ("Zərdab", "Zardab"),
)


def upgrade() -> None:
    connection = op.get_bind()
    country_id = connection.execute(sa.text("SELECT \"COUNTRY_ID\" FROM \"DIC_COUNTRIES\" WHERE \"ISO_CODE\" = 'AZ'" )).scalar_one()
    status_id = connection.execute(sa.text("SELECT \"STATUS_ID\" FROM \"DIC_STATUS\" WHERE lower(\"ENG_NAME\") = 'active' ORDER BY \"STATUS_ID\" LIMIT 1")).scalar_one()
    statement = sa.text('INSERT INTO "DIC_CITIES" ("COUNTRY_ID", "AZE_NAME", "ENG_NAME", "STATUS_ID") VALUES (:country_id, :aze_name, :eng_name, :status_id) ON CONFLICT ON CONSTRAINT uq_city_country_eng_name DO NOTHING')
    connection.execute(statement, [{"country_id": country_id, "aze_name": aze, "eng_name": eng, "status_id": status_id} for aze, eng in CITIES])


def downgrade() -> None:
    connection = op.get_bind()
    country_id = connection.execute(sa.text("SELECT \"COUNTRY_ID\" FROM \"DIC_COUNTRIES\" WHERE \"ISO_CODE\" = 'AZ'" )).scalar_one_or_none()
    if country_id is None:
        return
    names = [city[1] for city in CITIES]
    connection.execute(sa.text('DELETE FROM "DIC_CITIES" AS city WHERE city."COUNTRY_ID" = :country_id AND city."ENG_NAME" = ANY(:names) AND NOT EXISTS (SELECT 1 FROM "TBL_AIRPORTS" AS airport WHERE airport."CITY_ID" = city."CITY_ID")').bindparams(sa.bindparam("names", type_=sa.ARRAY(sa.String()))), {"country_id": country_id, "names": names})
