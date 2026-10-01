import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Airport
from app.modules.airports.repository import AirportRepository
from app.modules.airports.schemas import (
    AirportCreate,
    AirportListResponse,
    AirportResponse,
)


class AirportNotFoundError(ValueError):
    pass


class AirportConflictError(ValueError):
    pass


class AirportValidationError(ValueError):
    pass


class AirportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AirportRepository(session)

    @staticmethod
    def _response(row: Any) -> AirportResponse:
        airport = row[0]
        return AirportResponse(
            air_id=airport.AIR_ID,
            icao_id=airport.ICAO_ID,
            icao_code=row.ICAO_CODE,
            iata_code=airport.IATA_CODE,
            aze_name=airport.AZE_NAME,
            eng_name=airport.ENG_NAME,
            country_id=airport.COUNTRY_ID,
            country_name=row.country_name,
            city_id=airport.CITY_ID,
            city_name=row.city_name,
            elevation_m=airport.ELEVATION_M,
            arp_geom=json.loads(row.arp_geojson),
            boundary_geom=json.loads(row.boundary_geojson),
            status_id=airport.STATUS_ID,
            status=row.status_name,
            created_date=airport.CREATED_DATE,
            last_edited_date=airport.LAST_EDITED_DATE,
        )

    async def list_airports(self, **filters: Any) -> AirportListResponse:
        page = int(filters.pop("page"))
        page_size = int(filters.pop("page_size"))
        rows, total = await self.repository.list_airports(
            offset=(page - 1) * page_size,
            limit=page_size,
            **filters,
        )
        return AirportListResponse(
            items=[self._response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_airport(self, air_id: int) -> AirportResponse:
        row = await self.repository.get_airport(air_id)
        if row is None:
            raise AirportNotFoundError("Airport does not exist")
        return self._response(row)

    async def _validate_references(
        self,
        *,
        icao_id: int,
        country_id: int,
        city_id: int,
    ) -> None:
        error = await self.repository.validate_references(
            icao_id=icao_id,
            country_id=country_id,
            city_id=city_id,
        )
        if error:
            raise AirportValidationError(error)

    async def create_airport(self, payload: AirportCreate) -> AirportResponse:
        await self._validate_references(
            icao_id=payload.icao_id,
            country_id=payload.country_id,
            city_id=payload.city_id,
        )
        if await self.repository.find_duplicate(
            icao_id=payload.icao_id,
            iata_code=payload.iata_code,
        ):
            raise AirportConflictError("ICAO or IATA code is already assigned")
        active = await self.repository.get_status_by_name("active")
        if active is None:
            raise AirportValidationError("Active status is not configured")
        airport = Airport(
            ICAO_ID=payload.icao_id,
            IATA_CODE=payload.iata_code,
            AZE_NAME=payload.aze_name,
            ENG_NAME=payload.eng_name,
            COUNTRY_ID=payload.country_id,
            CITY_ID=payload.city_id,
            ELEVATION_M=payload.elevation_m,
            ARP_GEOM=self.repository.geometry(payload.arp_geom.model_dump()),
            BOUNDARY_GEOM=self.repository.geometry(payload.boundary_geom.model_dump()),
            STATUS_ID=active.STATUS_ID,
        )
        await self.repository.create(airport)
        await self.session.commit()
        return await self.get_airport(airport.AIR_ID)

    async def update_airport(
        self,
        air_id: int,
        changes: dict[str, Any],
    ) -> AirportResponse:
        airport = await self.repository.get_model(air_id)
        if airport is None:
            raise AirportNotFoundError("Airport does not exist")
        icao_id = int(changes.get("icao_id", airport.ICAO_ID))
        country_id = int(changes.get("country_id", airport.COUNTRY_ID))
        city_id = int(changes.get("city_id", airport.CITY_ID))
        await self._validate_references(
            icao_id=icao_id,
            country_id=country_id,
            city_id=city_id,
        )
        iata = changes.get("iata_code", airport.IATA_CODE)
        if await self.repository.find_duplicate(
            icao_id=icao_id if "icao_id" in changes else None,
            iata_code=str(iata) if "iata_code" in changes and iata else None,
            exclude_air_id=air_id,
        ):
            raise AirportConflictError("ICAO or IATA code is already assigned")

        fields = {
            "icao_id": "ICAO_ID",
            "iata_code": "IATA_CODE",
            "aze_name": "AZE_NAME",
            "eng_name": "ENG_NAME",
            "country_id": "COUNTRY_ID",
            "city_id": "CITY_ID",
            "elevation_m": "ELEVATION_M",
        }
        for source, target in fields.items():
            if source in changes:
                setattr(airport, target, changes[source])
        if changes.get("arp_geom") is not None:
            airport.ARP_GEOM = self.repository.geometry(changes["arp_geom"])
        if changes.get("boundary_geom") is not None:
            airport.BOUNDARY_GEOM = self.repository.geometry(changes["boundary_geom"])
        await self.session.commit()
        return await self.get_airport(air_id)

    async def update_status(self, air_id: int, status_id: int) -> AirportResponse:
        airport = await self.repository.get_model(air_id)
        if airport is None:
            raise AirportNotFoundError("Airport does not exist")
        if await self.repository.get_status(status_id) is None:
            raise AirportValidationError("Status does not exist")
        airport.STATUS_ID = status_id
        await self.session.commit()
        return await self.get_airport(air_id)

    async def archive(self, air_id: int) -> None:
        airport = await self.repository.get_model(air_id)
        if airport is None:
            raise AirportNotFoundError("Airport does not exist")
        archived = await self.repository.get_status_by_name("archived")
        if archived is None:
            raise AirportValidationError("Archived status is not configured")
        airport.STATUS_ID = archived.STATUS_ID
        await self.session.commit()
