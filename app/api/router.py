from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import check_database
from app.modules.airports.router import router as airports_router
from app.modules.auth.router import router as auth_router
from app.modules.dictionaries.router import router as dictionaries_router
from app.modules.declared_distances.router import router as declared_distances_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.dtm.router import router as dtm_router
from app.modules.runways.router import router as runways_router
from app.modules.ols.router import data_router as ols_data_router, router as ols_router
from app.modules.ols_revisions.router import router as ols_revisions_router
from app.modules.obstacles.router import router as obstacles_router
from app.modules.violations.router import router as violations_router
from app.modules.standards.router import router as standards_router
from app.modules.users.router import router as users_router
from app.modules.gis_import.router import router as gis_import_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(users_router)
api_router.include_router(dictionaries_router)
api_router.include_router(airports_router)
api_router.include_router(runways_router)
api_router.include_router(declared_distances_router)
api_router.include_router(standards_router)
api_router.include_router(ols_router)
api_router.include_router(ols_data_router)
api_router.include_router(ols_revisions_router)
api_router.include_router(dtm_router)
api_router.include_router(obstacles_router)
api_router.include_router(violations_router)
api_router.include_router(gis_import_router)


@api_router.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    try:
        postgis_version = await check_database()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        ) from exc

    return {
        "status": "ok",
        "database": "connected",
        "postgis": postgis_version,
    }
