from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DashboardTotals(BaseModel):
    airports: int
    runways: int
    ols_surfaces: int
    obstacles: int
    violations: int
    standards: int


class DashboardAirport(BaseModel):
    air_id: int
    icao_code: str
    name: str
    city: str
    status: str
    runway_count: int
    ols_surface_count: int
    obstacle_count: int
    violation_count: int


class DashboardObstacle(BaseModel):
    obstacle_id: int
    air_id: int
    airport_name: str
    name: str | None
    obstacle_type: str
    top_elevation_m: Decimal | None
    status: str
    created_date: datetime


class DashboardViolation(BaseModel):
    violation_id: int
    air_id: int
    obstacle_id: int
    obstacle_name: str | None
    surface_type: str
    penetration_m: Decimal | None
    status: str
    checked_date: datetime


class DashboardOverview(BaseModel):
    totals: DashboardTotals
    airports: list[DashboardAirport]
    ols_by_type: dict[str, int]
    obstacles_by_type: dict[str, int]
    violations_by_status: dict[str, int]
    recent_obstacles: list[DashboardObstacle]
    recent_violations: list[DashboardViolation]
    generated_at: datetime
