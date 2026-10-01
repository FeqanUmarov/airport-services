from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DatabaseSession
from app.modules.dashboard.schemas import DashboardOverview
from app.modules.dashboard.service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(current: CurrentUser, session: DatabaseSession) -> DashboardOverview:
    del current
    return await DashboardService(session).overview()
