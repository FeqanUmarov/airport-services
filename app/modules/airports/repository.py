import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Airport, City, Country, IcaoCode, Status


class AirportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _details_statement():
        return (
            select(
                Airport,
                IcaoCode.ICAO_CODE,
                Country.ENG_NAME.label("country_name"),
                City.ENG_NAME.label("city_name"),
                Status.ENG_NAME.label("status_name"),
                func.ST_AsGeoJSON(Airport.ARP_GEOM).label("arp_geojson"),
                func.ST_AsGeoJSON(Airport.BOUNDARY_GEOM).label("boundary_geojson"),
            )
            .join(IcaoCode, IcaoCode.ICAO_ID == Airport.ICAO_ID)
            .join(Country, Country.COUNTRY_ID == Airport.COUNTRY_ID)
            .join(City, City.CITY_ID == Airport.CITY_ID)
            .join(Status, Status.STATUS_ID == Airport.STATUS_ID)
        )

    async def list_airports(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None,
        country_id: int | None,
        city_id: int | None,
        status_id: int | None,
    ) -> tuple[list[Any], int]:
        conditions = []
        if search:
            pattern = f"%{search.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Airport.AZE_NAME).like(pattern),
                    func.lower(Airport.ENG_NAME).like(pattern),
                    func.lower(IcaoCode.ICAO_CODE).like(pattern),
                    func.lower(Airport.IATA_CODE).like(pattern),
                )
            )
        if country_id is not None:
            conditions.append(Airport.COUNTRY_ID == country_id)
        if city_id is not None:
            conditions.append(Airport.CITY_ID == city_id)
        if status_id is not None:
            conditions.append(Airport.STATUS_ID == status_id)

        base = self._details_statement().where(*conditions)
        count_statement = (
            select(func.count(Airport.AIR_ID))
            .join(IcaoCode, IcaoCode.ICAO_ID == Airport.ICAO_ID)
            .where(*conditions)
        )
        total = int((await self.session.scalar(count_statement)) or 0)
        rows = (
            await self.session.execute(
                base.order_by(Airport.AIR_ID).offset(offset).limit(limit)
            )
        ).all()
        return list(rows), total

    async def get_airport(self, air_id: int):
        return (
            await self.session.execute(
                self._details_statement().where(Airport.AIR_ID == air_id)
            )
        ).one_or_none()

    async def get_model(self, air_id: int) -> Airport | None:
        return await self.session.get(Airport, air_id)

    async def get_status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def get_status_by_name(self, name: str) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == name.casefold())
        )

    async def validate_references(
        self,
        *,
        icao_id: int,
        country_id: int,
        city_id: int,
    ) -> str | None:
        icao = await self.session.get(IcaoCode, icao_id)
        country = await self.session.get(Country, country_id)
        city = await self.session.get(City, city_id)
        if icao is None:
            return "ICAO code does not exist"
        if country is None:
            return "Country does not exist"
        if city is None:
            return "City does not exist"
        if city.COUNTRY_ID != country_id:
            return "City does not belong to the selected country"
        return None

    async def find_duplicate(
        self,
        *,
        icao_id: int | None,
        iata_code: str | None,
        exclude_air_id: int | None = None,
    ) -> Airport | None:
        conditions = []
        if icao_id is not None:
            conditions.append(Airport.ICAO_ID == icao_id)
        if iata_code:
            conditions.append(func.lower(Airport.IATA_CODE) == iata_code.lower())
        if not conditions:
            return None
        statement = select(Airport).where(or_(*conditions))
        if exclude_air_id is not None:
            statement = statement.where(Airport.AIR_ID != exclude_air_id)
        return await self.session.scalar(statement)

    @staticmethod
    def geometry(value: dict[str, Any]):
        return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), 4326)

    async def create(self, airport: Airport) -> None:
        self.session.add(airport)
        await self.session.flush()
