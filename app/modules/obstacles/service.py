import json
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.obstacles.models import Obstacle
from app.modules.obstacles.repository import ObstacleRepository
from app.modules.obstacles.schemas import ObstacleGeoJsonResponse,ObstacleListResponse,ObstacleResponse
class ObstacleNotFoundError(ValueError): pass
class ObstacleValidationError(ValueError): pass
class ObstacleService:
    def __init__(self,session:AsyncSession): self.session=session; self.repo=ObstacleRepository(session)
    @staticmethod
    def out(row):
        x=row[0]; return ObstacleResponse(obstacle_id=x.OBSTACLE_ID,air_id=x.AIR_ID,airport_name=row.airport_name,dtm_id=x.DTM_ID,dtm_name=row.dtm_name,aze_name=x.AZE_NAME,eng_name=x.ENG_NAME,obstacle_type_id=x.OBSTACLE_TYPE_ID,obstacle_type_code=row.type_code,obstacle_type_name=row.type_name,ground_elevation_m=x.GROUND_ELEVATION_M,object_height_m=x.OBJECT_HEIGHT_M,top_elevation_m=x.TOP_ELEVATION_M,geometry=json.loads(row.geojson),status_id=x.STATUS_ID,status=row.status_name,created_date=x.CREATED_DATE,last_edited_date=x.LAST_EDITED_DATE)
    async def validate_links(self,air_id,type_id,dtm_id):
        if not await self.repo.airport(air_id): raise ObstacleNotFoundError("Airport does not exist")
        if not await self.repo.obstacle_type(type_id): raise ObstacleValidationError("Obstacle type does not exist")
        if dtm_id:
            dtm=await self.repo.dtm(dtm_id)
            if not dtm: raise ObstacleValidationError("DTM source does not exist")
            if dtm.AIR_ID!=air_id: raise ObstacleValidationError("DTM source belongs to another airport")
    async def get(self,id):
        row=await self.repo.row(id)
        if not row: raise ObstacleNotFoundError("Obstacle does not exist")
        return self.out(row)
    async def list(self,air_id,page,size,search,type_id,status_id):
        if not await self.repo.airport(air_id): raise ObstacleNotFoundError("Airport does not exist")
        rows,total=await self.repo.list(air_id,(page-1)*size,size,search,type_id,status_id); return ObstacleListResponse(items=[self.out(r) for r in rows],total=total,page=page,page_size=size)
    async def geojson(self,air_id,status_id):
        if not await self.repo.airport(air_id): raise ObstacleNotFoundError("Airport does not exist")
        rows=await self.repo.all_rows(air_id,status_id); features=[]
        for r in rows:
            x=self.out(r); features.append({"type":"Feature","id":x.obstacle_id,"geometry":x.geometry,"properties":x.model_dump(exclude={"geometry"},mode="json")})
        return ObstacleGeoJsonResponse(features=features)
    async def create(self,air_id,p):
        await self.validate_links(air_id,p.obstacle_type_id,p.dtm_id); active=await self.repo.named_status("active")
        if not active: raise ObstacleValidationError("Active status is not configured")
        x=Obstacle(AIR_ID=air_id,DTM_ID=p.dtm_id,AZE_NAME=p.aze_name,ENG_NAME=p.eng_name,OBSTACLE_TYPE_ID=p.obstacle_type_id,GROUND_ELEVATION_M=p.ground_elevation_m,OBJECT_HEIGHT_M=p.object_height_m,TOP_ELEVATION_M=p.top_elevation_m,GEOM=self.repo.geom(p.geometry.model_dump()),STATUS_ID=active.STATUS_ID)
        self.session.add(x); await self.session.commit(); return await self.get(x.OBSTACLE_ID)
    @staticmethod
    def elevations(x,c):
        ground=c.get("ground_elevation_m",x.GROUND_ELEVATION_M); height=c.get("object_height_m",x.OBJECT_HEIGHT_M); top=c.get("top_elevation_m",x.TOP_ELEVATION_M)
        if ground is None and top is None: raise ObstacleValidationError("ground_elevation_m or top_elevation_m is required; terrain elevation is never invented")
        if ground is not None and height is not None:
            calculated=Decimal(str(ground))+Decimal(str(height))
            if "top_elevation_m" in c and top is not None and abs(Decimal(str(top))-calculated)>Decimal("0.001"): raise ObstacleValidationError("top_elevation_m must equal ground_elevation_m + object_height_m")
            top=calculated
        return ground,height,top
    async def update(self,id,c):
        x=await self.repo.model(id)
        if not x: raise ObstacleNotFoundError("Obstacle does not exist")
        await self.validate_links(x.AIR_ID,int(c.get("obstacle_type_id",x.OBSTACLE_TYPE_ID)),c.get("dtm_id",x.DTM_ID)); ground,height,top=self.elevations(x,c)
        for a,b in {"dtm_id":"DTM_ID","aze_name":"AZE_NAME","eng_name":"ENG_NAME","obstacle_type_id":"OBSTACLE_TYPE_ID"}.items():
            if a in c: setattr(x,b,c[a])
        x.GROUND_ELEVATION_M=ground; x.OBJECT_HEIGHT_M=height; x.TOP_ELEVATION_M=top
        if "geometry" in c: x.GEOM=self.repo.geom(c["geometry"])
        await self.session.commit(); return await self.get(id)
    async def status(self,id,status_id):
        x=await self.repo.model(id)
        if not x: raise ObstacleNotFoundError("Obstacle does not exist")
        if not await self.repo.status(status_id): raise ObstacleValidationError("Status does not exist")
        x.STATUS_ID=status_id; await self.session.commit()
    async def archive(self,id):
        x=await self.repo.model(id)
        if not x: raise ObstacleNotFoundError("Obstacle does not exist")
        s=await self.repo.named_status("archived")
        if not s: raise ObstacleValidationError("Archived status is not configured")
        x.STATUS_ID=s.STATUS_ID; await self.session.commit()
