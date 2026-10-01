import json
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.airports.models import Airport, Status
from app.modules.dtm.models import DtmSource

class DtmRepository:
    def __init__(self,session:AsyncSession): self.session=session
    @staticmethod
    def details():
        return select(DtmSource,Airport.ENG_NAME.label("airport_name"),Status.ENG_NAME.label("status_name"),func.ST_AsGeoJSON(DtmSource.COVERAGE_GEOM).label("coverage_geojson")).join(Airport,Airport.AIR_ID==DtmSource.AIR_ID).join(Status,Status.STATUS_ID==DtmSource.STATUS_ID)
    async def list(self,air_id,offset,limit,search,status_id):
        c=[DtmSource.AIR_ID==air_id]
        if search:
            p=f"%{search.strip().lower()}%"; c.append(or_(func.lower(DtmSource.NAME).like(p),func.lower(DtmSource.SOURCE_PATH).like(p)))
        if status_id: c.append(DtmSource.STATUS_ID==status_id)
        total=int(await self.session.scalar(select(func.count(DtmSource.DTM_ID)).where(*c)) or 0)
        rows=(await self.session.execute(self.details().where(*c).order_by(DtmSource.IS_PRIMARY.desc(),DtmSource.DTM_ID.desc()).offset(offset).limit(limit))).all()
        return rows,total
    async def row(self,id): return (await self.session.execute(self.details().where(DtmSource.DTM_ID==id))).one_or_none()
    async def model(self,id): return await self.session.get(DtmSource,id)
    async def airport(self,id): return await self.session.get(Airport,id)
    async def status(self,id): return await self.session.get(Status,id)
    async def named_status(self,name): return await self.session.scalar(select(Status).where(func.lower(Status.ENG_NAME)==name.casefold()))
    async def clear_primary(self,air_id,exclude=None):
        q=update(DtmSource).where(DtmSource.AIR_ID==air_id)
        if exclude: q=q.where(DtmSource.DTM_ID!=exclude)
        await self.session.execute(q.values(IS_PRIMARY=False))
    async def active(self,air_id,status_id):
        return (await self.session.execute(self.details().where(DtmSource.AIR_ID==air_id,DtmSource.STATUS_ID==status_id).order_by(DtmSource.IS_PRIMARY.desc(),DtmSource.RESOLUTION_M.asc().nullslast()).limit(1))).one_or_none()
    async def applicable_model(self,air_id,status_id,longitude,latitude):
        point=func.ST_SetSRID(func.ST_MakePoint(longitude,latitude),4326)
        return await self.session.scalar(select(DtmSource).where(DtmSource.AIR_ID==air_id,DtmSource.STATUS_ID==status_id,or_(DtmSource.COVERAGE_GEOM.is_(None),func.ST_Covers(DtmSource.COVERAGE_GEOM,point))).order_by(DtmSource.IS_PRIMARY.desc(),DtmSource.RESOLUTION_M.asc().nullslast(),DtmSource.DTM_ID.desc()).limit(1))
    @staticmethod
    def geom(value): return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)),4326)
