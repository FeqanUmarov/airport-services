from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import DashboardAirport, DashboardObstacle, DashboardOverview, DashboardTotals, DashboardViolation


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DashboardRepository(session)

    async def overview(self) -> DashboardOverview:
        totals = await self.repository.totals()
        airports = [DashboardAirport(air_id=row.AIR_ID, icao_code=row.ICAO_CODE, name=row.AZE_NAME, city=row.city, status=row.status, runway_count=row.runways, ols_surface_count=row.ols, obstacle_count=row.obstacles, violation_count=row.violations) for row in await self.repository.airport_rows()]
        obstacles = [DashboardObstacle(obstacle_id=row[0].OBSTACLE_ID, air_id=row[0].AIR_ID, airport_name=row.airport, name=row[0].AZE_NAME or row[0].ENG_NAME, obstacle_type=row.type, top_elevation_m=row[0].TOP_ELEVATION_M, status=row.status, created_date=row[0].CREATED_DATE) for row in await self.repository.recent_obstacles()]
        violations = [DashboardViolation(violation_id=row[0].VIOLATION_ID, air_id=row.AIR_ID, obstacle_id=row[0].OBSTACLE_ID, obstacle_name=row.obstacle, surface_type=row.surface_type, penetration_m=row[0].PENETRATION_M, status=row.status, checked_date=row[0].LAST_CHECKED_DATE) for row in await self.repository.recent_violations()]
        return DashboardOverview(totals=DashboardTotals(**totals), airports=airports, ols_by_type=await self.repository.ols_by_type(), obstacles_by_type=await self.repository.obstacles_by_type(), violations_by_status=await self.repository.violations_by_status(), recent_obstacles=obstacles, recent_violations=violations, generated_at=datetime.now(UTC))
