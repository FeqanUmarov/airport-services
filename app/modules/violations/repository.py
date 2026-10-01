from __future__ import annotations

from sqlalchemy import delete,func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.airports.models import Airport,Status
from app.modules.obstacles.models import Obstacle,ObstacleType,OlsViolation
from app.modules.ols.models import OlsSurface,OlsSurfaceType,StandardOlsSurface

class ViolationRepository:
    def __init__(self,session:AsyncSession): self.session=session
    @staticmethod
    def details():
        return select(OlsViolation,Obstacle.ENG_NAME.label("obstacle_eng"),Obstacle.AZE_NAME.label("obstacle_aze"),ObstacleType.CODE.label("obstacle_type"),OlsSurface.ENG_NAME.label("surface_eng"),OlsSurface.AZE_NAME.label("surface_aze"),OlsSurfaceType.CODE.label("surface_type"),Status.ENG_NAME.label("status_name")).join(Obstacle,Obstacle.OBSTACLE_ID==OlsViolation.OBSTACLE_ID).join(ObstacleType,ObstacleType.OBSTACLE_TYPE_ID==Obstacle.OBSTACLE_TYPE_ID).join(OlsSurface,OlsSurface.OLS_SURFACE_ID==OlsViolation.OLS_SURFACE_ID).join(StandardOlsSurface,StandardOlsSurface.STANDARD_OLS_ID==OlsSurface.STANDARD_OLS_ID).join(OlsSurfaceType,OlsSurfaceType.SURFACE_TYPE_ID==StandardOlsSurface.SURFACE_TYPE_ID).join(Status,Status.STATUS_ID==OlsViolation.STATUS_ID)
    async def obstacle(self,id): return await self.session.get(Obstacle,id)
    async def airport(self,id): return await self.session.get(Airport,id)
    async def violation(self,id): return await self.session.get(OlsViolation,id)
    async def status(self,id): return await self.session.get(Status,id)
    async def named_status(self,name): return await self.session.scalar(select(Status).where(func.lower(Status.ENG_NAME)==name.casefold()))
    async def row(self,id): return (await self.session.execute(self.details().where(OlsViolation.VIOLATION_ID==id))).one_or_none()
    async def list(self,*,air_id=None,obstacle_id=None,offset=0,limit=20,status_id=None,surface_type=None):
        c=[]
        if air_id: c.append(Obstacle.AIR_ID==air_id)
        if obstacle_id: c.append(OlsViolation.OBSTACLE_ID==obstacle_id)
        if status_id: c.append(OlsViolation.STATUS_ID==status_id)
        if surface_type: c.append(OlsSurfaceType.CODE==surface_type.upper())
        base=self.details().where(*c); total=int(await self.session.scalar(select(func.count(OlsViolation.VIOLATION_ID)).join(Obstacle,Obstacle.OBSTACLE_ID==OlsViolation.OBSTACLE_ID).join(OlsSurface,OlsSurface.OLS_SURFACE_ID==OlsViolation.OLS_SURFACE_ID).join(StandardOlsSurface,StandardOlsSurface.STANDARD_OLS_ID==OlsSurface.STANDARD_OLS_ID).join(OlsSurfaceType,OlsSurfaceType.SURFACE_TYPE_ID==StandardOlsSurface.SURFACE_TYPE_ID).where(*c)) or 0)
        return (await self.session.execute(base.order_by(OlsViolation.PENETRATION_M.desc()).offset(offset).limit(limit))).all(),total
    async def candidate_surfaces(self,obstacle:Obstacle,active_status_id:int):
        point=func.ST_PointOnSurface(func.ST_Force2D(obstacle.GEOM))
        return (await self.session.execute(select(OlsSurface,OlsSurfaceType.CODE.label("surface_type"),func.coalesce(OlsSurface.ENG_NAME,OlsSurface.AZE_NAME,OlsSurfaceType.ENG_NAME,OlsSurfaceType.CODE).label("surface_name"),func.ST_AsGeoJSON(OlsSurface.GEOM).label("surface_geojson"),func.ST_X(point).label("x"),func.ST_Y(point).label("y")).join(StandardOlsSurface,StandardOlsSurface.STANDARD_OLS_ID==OlsSurface.STANDARD_OLS_ID).join(OlsSurfaceType,OlsSurfaceType.SURFACE_TYPE_ID==StandardOlsSurface.SURFACE_TYPE_ID).where(OlsSurface.AIR_ID==obstacle.AIR_ID,OlsSurface.STATUS_ID==active_status_id,func.ST_Intersects(func.ST_Force2D(OlsSurface.GEOM),point)))).all()
    async def candidate_surfaces_for_geometry(self,air_id:int,geometry:dict,active_status_id:int):
        import json
        geom=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)),4326); point=func.ST_PointOnSurface(func.ST_Force2D(geom))
        return (await self.session.execute(select(OlsSurface,OlsSurfaceType.CODE.label("surface_type"),func.coalesce(OlsSurface.ENG_NAME,OlsSurface.AZE_NAME,OlsSurfaceType.ENG_NAME,OlsSurfaceType.CODE).label("surface_name"),func.ST_AsGeoJSON(OlsSurface.GEOM).label("surface_geojson"),func.ST_X(point).label("x"),func.ST_Y(point).label("y")).join(StandardOlsSurface,StandardOlsSurface.STANDARD_OLS_ID==OlsSurface.STANDARD_OLS_ID).join(OlsSurfaceType,OlsSurfaceType.SURFACE_TYPE_ID==StandardOlsSurface.SURFACE_TYPE_ID).where(OlsSurface.AIR_ID==air_id,OlsSurface.STATUS_ID==active_status_id,func.ST_Intersects(func.ST_Force2D(OlsSurface.GEOM),point)))).all()
    async def representative_point(self,geometry:dict):
        import json
        geom=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)),4326); point=func.ST_PointOnSurface(func.ST_Force2D(geom))
        return (await self.session.execute(select(func.ST_X(point),func.ST_Y(point)))).one()
    async def replace(self,obstacle_id:int,values:list[dict]):
        await self.session.execute(delete(OlsViolation).where(OlsViolation.OBSTACLE_ID==obstacle_id))
        items=[OlsViolation(**v) for v in values]; self.session.add_all(items); await self.session.flush(); return items
