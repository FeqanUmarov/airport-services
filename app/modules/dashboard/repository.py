from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Airport, City, IcaoCode, Status
from app.modules.obstacles.models import Obstacle, ObstacleType, OlsViolation
from app.modules.ols.models import OlsSurface, OlsSurfaceType, Standard, StandardOlsSurface
from app.modules.runways.models import Runway


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count(self, model: type) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(model)) or 0)

    async def totals(self) -> dict[str, int]:
        return {
            "airports": await self.count(Airport),
            "runways": await self.count(Runway),
            "ols_surfaces": await self.count(OlsSurface),
            "obstacles": await self.count(Obstacle),
            "violations": await self.count(OlsViolation),
            "standards": await self.count(Standard),
        }

    async def grouped_counts(self, statement: Select) -> dict[str, int]:
        rows = (await self.session.execute(statement)).all()
        return {str(label): int(total) for label, total in rows}

    async def ols_by_type(self) -> dict[str, int]:
        return await self.grouped_counts(
            select(OlsSurfaceType.CODE, func.count(OlsSurface.OLS_SURFACE_ID))
            .join(StandardOlsSurface, StandardOlsSurface.SURFACE_TYPE_ID == OlsSurfaceType.SURFACE_TYPE_ID)
            .join(OlsSurface, OlsSurface.STANDARD_OLS_ID == StandardOlsSurface.STANDARD_OLS_ID)
            .group_by(OlsSurfaceType.CODE)
            .order_by(func.count(OlsSurface.OLS_SURFACE_ID).desc())
        )

    async def obstacles_by_type(self) -> dict[str, int]:
        return await self.grouped_counts(
            select(ObstacleType.AZE_NAME, func.count(Obstacle.OBSTACLE_ID))
            .join(Obstacle, Obstacle.OBSTACLE_TYPE_ID == ObstacleType.OBSTACLE_TYPE_ID)
            .group_by(ObstacleType.AZE_NAME)
            .order_by(func.count(Obstacle.OBSTACLE_ID).desc())
        )

    async def violations_by_status(self) -> dict[str, int]:
        return await self.grouped_counts(
            select(Status.AZE_NAME, func.count(OlsViolation.VIOLATION_ID))
            .join(OlsViolation, OlsViolation.STATUS_ID == Status.STATUS_ID)
            .group_by(Status.AZE_NAME)
            .order_by(func.count(OlsViolation.VIOLATION_ID).desc())
        )

    async def airport_rows(self, limit: int = 8):
        runway_counts = select(Runway.AIR_ID.label("air_id"), func.count(Runway.RUN_ID).label("total")).group_by(Runway.AIR_ID).subquery()
        ols_counts = select(OlsSurface.AIR_ID.label("air_id"), func.count(OlsSurface.OLS_SURFACE_ID).label("total")).group_by(OlsSurface.AIR_ID).subquery()
        obstacle_counts = select(Obstacle.AIR_ID.label("air_id"), func.count(Obstacle.OBSTACLE_ID).label("total")).group_by(Obstacle.AIR_ID).subquery()
        violation_counts = (
            select(Obstacle.AIR_ID.label("air_id"), func.count(OlsViolation.VIOLATION_ID).label("total"))
            .join(OlsViolation, OlsViolation.OBSTACLE_ID == Obstacle.OBSTACLE_ID)
            .group_by(Obstacle.AIR_ID).subquery()
        )
        statement = (
            select(
                Airport.AIR_ID, Airport.AZE_NAME, IcaoCode.ICAO_CODE, City.AZE_NAME.label("city"), Status.AZE_NAME.label("status"),
                func.coalesce(runway_counts.c.total, 0).label("runways"), func.coalesce(ols_counts.c.total, 0).label("ols"),
                func.coalesce(obstacle_counts.c.total, 0).label("obstacles"), func.coalesce(violation_counts.c.total, 0).label("violations"),
            )
            .join(IcaoCode, IcaoCode.ICAO_ID == Airport.ICAO_ID).join(City, City.CITY_ID == Airport.CITY_ID).join(Status, Status.STATUS_ID == Airport.STATUS_ID)
            .outerjoin(runway_counts, runway_counts.c.air_id == Airport.AIR_ID).outerjoin(ols_counts, ols_counts.c.air_id == Airport.AIR_ID)
            .outerjoin(obstacle_counts, obstacle_counts.c.air_id == Airport.AIR_ID).outerjoin(violation_counts, violation_counts.c.air_id == Airport.AIR_ID)
            .order_by(Airport.LAST_EDITED_DATE.desc()).limit(limit)
        )
        return (await self.session.execute(statement)).all()

    async def recent_obstacles(self, limit: int = 6):
        statement = (
            select(Obstacle, Airport.AZE_NAME.label("airport"), ObstacleType.AZE_NAME.label("type"), Status.AZE_NAME.label("status"))
            .join(Airport, Airport.AIR_ID == Obstacle.AIR_ID).join(ObstacleType, ObstacleType.OBSTACLE_TYPE_ID == Obstacle.OBSTACLE_TYPE_ID)
            .join(Status, Status.STATUS_ID == Obstacle.STATUS_ID).order_by(Obstacle.CREATED_DATE.desc()).limit(limit)
        )
        return (await self.session.execute(statement)).all()

    async def recent_violations(self, limit: int = 6):
        statement = (
            select(OlsViolation, Obstacle.AIR_ID, Obstacle.AZE_NAME.label("obstacle"), OlsSurfaceType.CODE.label("surface_type"), Status.AZE_NAME.label("status"))
            .join(Obstacle, Obstacle.OBSTACLE_ID == OlsViolation.OBSTACLE_ID).join(OlsSurface, OlsSurface.OLS_SURFACE_ID == OlsViolation.OLS_SURFACE_ID)
            .join(StandardOlsSurface, StandardOlsSurface.STANDARD_OLS_ID == OlsSurface.STANDARD_OLS_ID)
            .join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID)
            .join(Status, Status.STATUS_ID == OlsViolation.STATUS_ID).order_by(OlsViolation.LAST_CHECKED_DATE.desc()).limit(limit)
        )
        return (await self.session.execute(statement)).all()
