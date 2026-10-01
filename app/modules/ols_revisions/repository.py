import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ols.models import OlsSurface
from app.modules.ols_revisions.models import OlsSurfaceRevision


class OlsRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_snapshot(self, surface: OlsSurface, *, change_type: str, note: str | None, user_id: int | None) -> OlsSurfaceRevision:
        # Read the materialized database row explicitly. Geometry may have been
        # assigned using a PostGIS SQL expression and remain expired in ORM state.
        surface_id = int(surface.__dict__["OLS_SURFACE_ID"])
        snapshot = (
            await self.session.execute(
                select(
                    OlsSurface.STANDARD_OLS_ID,
                    OlsSurface.GENERATION_METHOD_ID,
                    OlsSurface.AIR_ID,
                    OlsSurface.RUN_ID,
                    OlsSurface.RUN_DIR_ID,
                    OlsSurface.AZE_NAME,
                    OlsSurface.ENG_NAME,
                    OlsSurface.GEOM,
                    OlsSurface.STATUS_ID,
                ).where(OlsSurface.OLS_SURFACE_ID == surface_id)
            )
        ).one()
        revision_no = int((await self.session.scalar(select(func.coalesce(func.max(OlsSurfaceRevision.REVISION_NO), 0)).where(OlsSurfaceRevision.OLS_SURFACE_ID == surface_id))) or 0) + 1
        item = OlsSurfaceRevision(OLS_SURFACE_ID=surface_id,REVISION_NO=revision_no,STANDARD_OLS_ID=snapshot.STANDARD_OLS_ID,GENERATION_METHOD_ID=snapshot.GENERATION_METHOD_ID,AIR_ID=snapshot.AIR_ID,RUN_ID=snapshot.RUN_ID,RUN_DIR_ID=snapshot.RUN_DIR_ID,AZE_NAME=snapshot.AZE_NAME,ENG_NAME=snapshot.ENG_NAME,GEOM=snapshot.GEOM,STATUS_ID=snapshot.STATUS_ID,CHANGE_TYPE=change_type,CHANGE_NOTE=note,CREATED_BY=user_id)
        self.session.add(item); await self.session.flush(); return item

    async def surface(self, surface_id: int) -> OlsSurface | None:
        return await self.session.get(OlsSurface, surface_id)

    def details_statement(self):
        return select(OlsSurfaceRevision,func.ST_AsGeoJSON(OlsSurfaceRevision.GEOM).label("geojson"))

    async def list_rows(self, surface_id: int):
        return list((await self.session.execute(self.details_statement().where(OlsSurfaceRevision.OLS_SURFACE_ID==surface_id).order_by(OlsSurfaceRevision.REVISION_NO.desc()))).all())

    async def get_row(self, surface_id: int, revision_no: int):
        return (await self.session.execute(self.details_statement().where(OlsSurfaceRevision.OLS_SURFACE_ID==surface_id,OlsSurfaceRevision.REVISION_NO==revision_no))).one_or_none()
