import json
from sqlalchemy import func,or_,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.airports.models import Airport,Status
from app.modules.dtm.models import DtmSource
from app.modules.obstacles.models import Obstacle,ObstacleType

class ObstacleRepository:
    def __init__(self,session:AsyncSession): self.session=session
    @staticmethod
    def details():
        return select(Obstacle,Airport.ENG_NAME.label("airport_name"),DtmSource.NAME.label("dtm_name"),ObstacleType.CODE.label("type_code"),ObstacleType.ENG_NAME.label("type_name"),Status.ENG_NAME.label("status_name"),func.ST_AsGeoJSON(Obstacle.GEOM).label("geojson")).join(Airport,Airport.AIR_ID==Obstacle.AIR_ID).outerjoin(DtmSource,DtmSource.DTM_ID==Obstacle.DTM_ID).join(ObstacleType,ObstacleType.OBSTACLE_TYPE_ID==Obstacle.OBSTACLE_TYPE_ID).join(Status,Status.STATUS_ID==Obstacle.STATUS_ID)
    async def list(self,air_id,offset,limit,search,type_id,status_id):
        c=[Obstacle.AIR_ID==air_id]
        if search:
            p=f"%{search.strip().lower()}%"; c.append(or_(func.lower(Obstacle.AZE_NAME).like(p),func.lower(Obstacle.ENG_NAME).like(p)))
        if type_id: c.append(Obstacle.OBSTACLE_TYPE_ID==type_id)
        if status_id: c.append(Obstacle.STATUS_ID==status_id)
        total=int(await self.session.scalar(select(func.count(Obstacle.OBSTACLE_ID)).where(*c)) or 0)
        rows=(await self.session.execute(self.details().where(*c).order_by(Obstacle.OBSTACLE_ID.desc()).offset(offset).limit(limit))).all(); return rows,total
    async def all_rows(self,air_id,status_id=None):
        q=self.details().where(Obstacle.AIR_ID==air_id)
        if status_id: q=q.where(Obstacle.STATUS_ID==status_id)
        return (await self.session.execute(q.order_by(Obstacle.OBSTACLE_ID))).all()
    async def row(self,id): return (await self.session.execute(self.details().where(Obstacle.OBSTACLE_ID==id))).one_or_none()
    async def model(self,id): return await self.session.get(Obstacle,id)
    async def airport(self,id): return await self.session.get(Airport,id)
    async def dtm(self,id): return await self.session.get(DtmSource,id)
    async def obstacle_type(self,id): return await self.session.get(ObstacleType,id)
    async def status(self,id): return await self.session.get(Status,id)
    async def named_status(self,name): return await self.session.scalar(select(Status).where(func.lower(Status.ENG_NAME)==name.casefold()))
    @staticmethod
    def geom(value): return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(value)),4326)
