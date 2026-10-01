import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Airport, Status
from app.modules.runways.models import (
    Runway,
    RunwayArea,
    RunwayAreaType,
    RunwayDirection,
    RunwayStrip,
)


class RunwayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def geometry(value: dict[str, Any]):
        return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)), 4326)

    async def active_status(self) -> Status | None:
        return await self.status_by_name("active")

    async def status_by_name(self, name: str) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == name.casefold())
        )

    async def status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def airport_exists(self, air_id: int) -> bool:
        return await self.session.get(Airport, air_id) is not None

    async def airport(self, air_id: int) -> Airport | None:
        return await self.session.get(Airport, air_id)

    def runway_statement(self):
        return (
            select(
                Runway,
                Airport.ENG_NAME.label("airport_name"),
                Status.ENG_NAME.label("status_name"),
                func.ST_AsGeoJSON(Runway.GEOM).label("geojson"),
                func.ST_AsGeoJSON(Runway.CENTERLINE_GEOM).label("centerline_geojson"),
            )
            .join(Airport, Airport.AIR_ID == Runway.AIR_ID)
            .join(Status, Status.STATUS_ID == Runway.STATUS_ID)
        )

    async def list_runways(self, air_id: int, search: str | None, status_id: int | None):
        conditions = [Runway.AIR_ID == air_id]
        if search:
            pattern = f"%{search.strip().lower()}%"
            conditions.append(or_(func.lower(Runway.ENG_NAME).like(pattern), func.lower(Runway.DESIGNATOR_1).like(pattern), func.lower(Runway.DESIGNATOR_2).like(pattern)))
        if status_id is not None:
            conditions.append(Runway.STATUS_ID == status_id)
        return list((await self.session.execute(self.runway_statement().where(*conditions).order_by(Runway.RUN_ID))).all())

    async def runway_row(self, run_id: int):
        return (await self.session.execute(self.runway_statement().where(Runway.RUN_ID == run_id))).one_or_none()

    async def runway(self, run_id: int) -> Runway | None:
        return await self.session.get(Runway, run_id)

    async def duplicate_runway(self, air_id: int, d1: str, d2: str, exclude: int | None = None) -> Runway | None:
        statement = select(Runway).where(Runway.AIR_ID == air_id, Runway.DESIGNATOR_1 == d1, Runway.DESIGNATOR_2 == d2)
        if exclude is not None:
            statement = statement.where(Runway.RUN_ID != exclude)
        return await self.session.scalar(statement)

    def direction_statement(self):
        return select(RunwayDirection, Status.ENG_NAME.label("status_name"), func.ST_AsGeoJSON(RunwayDirection.THRESHOLD_GEOM).label("geojson")).join(Status, Status.STATUS_ID == RunwayDirection.STATUS_ID)

    async def direction_rows(self, run_id: int):
        return list((await self.session.execute(self.direction_statement().where(RunwayDirection.RUN_ID == run_id).order_by(RunwayDirection.RUN_DIR_ID))).all())

    async def direction_row(self, direction_id: int):
        return (await self.session.execute(self.direction_statement().where(RunwayDirection.RUN_DIR_ID == direction_id))).one_or_none()

    async def direction(self, direction_id: int) -> RunwayDirection | None:
        return await self.session.get(RunwayDirection, direction_id)

    async def duplicate_direction(self, run_id: int, designator: str, exclude: int | None = None) -> RunwayDirection | None:
        statement = select(RunwayDirection).where(RunwayDirection.RUN_ID == run_id, RunwayDirection.DESIGNATOR == designator)
        if exclude is not None:
            statement = statement.where(RunwayDirection.RUN_DIR_ID != exclude)
        return await self.session.scalar(statement)

    def strip_statement(self):
        return select(RunwayStrip, Status.ENG_NAME.label("status_name"), func.ST_AsGeoJSON(RunwayStrip.GEOM).label("geojson")).join(Status, Status.STATUS_ID == RunwayStrip.STATUS_ID)

    async def strip_row(self, run_id: int):
        return (await self.session.execute(self.strip_statement().where(RunwayStrip.RUN_ID == run_id))).one_or_none()

    async def strip(self, run_id: int) -> RunwayStrip | None:
        return await self.session.scalar(select(RunwayStrip).where(RunwayStrip.RUN_ID == run_id))

    def area_statement(self):
        return select(RunwayArea, RunwayAreaType.CODE.label("area_type_code"), Status.ENG_NAME.label("status_name"), func.ST_AsGeoJSON(RunwayArea.GEOM).label("geojson")).join(RunwayAreaType, RunwayAreaType.AREA_TYPE_ID == RunwayArea.AREA_TYPE_ID).join(Status, Status.STATUS_ID == RunwayArea.STATUS_ID)

    async def area_rows(self, direction_id: int):
        return list((await self.session.execute(self.area_statement().where(RunwayArea.RUN_DIR_ID == direction_id, func.upper(RunwayAreaType.CODE) != "RESA").order_by(RunwayArea.RUNWAY_AREA_ID))).all())

    async def area_row(self, area_id: int):
        return (await self.session.execute(self.area_statement().where(RunwayArea.RUNWAY_AREA_ID == area_id))).one_or_none()

    async def area(self, area_id: int) -> RunwayArea | None:
        return await self.session.get(RunwayArea, area_id)

    async def area_type_exists(self, area_type_id: int) -> bool:
        return await self.session.get(RunwayAreaType, area_type_id) is not None

    async def area_type_by_code(self, code: str) -> RunwayAreaType | None:
        return await self.session.scalar(
            select(RunwayAreaType).where(func.upper(RunwayAreaType.CODE) == code.upper())
        )

    async def duplicate_area(self, direction_id: int, area_type_id: int, exclude: int | None = None) -> RunwayArea | None:
        statement = select(RunwayArea).where(RunwayArea.RUN_DIR_ID == direction_id, RunwayArea.AREA_TYPE_ID == area_type_id)
        if exclude is not None:
            statement = statement.where(RunwayArea.RUNWAY_AREA_ID != exclude)
        return await self.session.scalar(statement)
