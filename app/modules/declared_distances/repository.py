from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Status
from app.modules.declared_distances.models import DeclaredDistance
from app.modules.runways.models import RunwayDirection


class DeclaredDistanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def details_statement(self):
        return (
            select(
                DeclaredDistance,
                RunwayDirection.RUN_ID,
                RunwayDirection.DESIGNATOR,
                Status.ENG_NAME.label("status_name"),
            )
            .join(
                RunwayDirection,
                RunwayDirection.RUN_DIR_ID == DeclaredDistance.RUN_DIR_ID,
            )
            .join(Status, Status.STATUS_ID == DeclaredDistance.STATUS_ID)
        )

    async def get_row_by_direction(self, direction_id: int):
        return (
            await self.session.execute(
                self.details_statement().where(
                    DeclaredDistance.RUN_DIR_ID == direction_id
                )
            )
        ).one_or_none()

    async def get_model_by_direction(self, direction_id: int) -> DeclaredDistance | None:
        return await self.session.scalar(
            select(DeclaredDistance).where(
                DeclaredDistance.RUN_DIR_ID == direction_id
            )
        )

    async def direction_exists(self, direction_id: int) -> bool:
        return await self.session.get(RunwayDirection, direction_id) is not None

    async def get_status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def status_by_name(self, name: str) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == name.casefold())
        )
