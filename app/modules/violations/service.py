import json,math
from decimal import Decimal
from itertools import combinations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from app.modules.violations.repository import ViolationRepository
from app.modules.violations.schemas import ObstacleAnalysisResponse,ViolationListResponse,ViolationResponse,ViolationSummary
from app.modules.violations.schemas import ManualObstacleCheckResponse,SurfaceCheckResult
from app.modules.dtm.repository import DtmRepository
from app.modules.dtm.sampler import DtmSampler,DtmSamplingError
from app.modules.obstacles.models import Obstacle,ObstacleType
class ViolationNotFoundError(ValueError): pass
class ViolationValidationError(ValueError): pass
class ViolationService:
    def __init__(self,session:AsyncSession): self.session=session; self.repo=ViolationRepository(session)
    @staticmethod
    def out(row):
        x=row[0]; return ViolationResponse(violation_id=x.VIOLATION_ID,obstacle_id=x.OBSTACLE_ID,obstacle_name=row.obstacle_eng or row.obstacle_aze,obstacle_type=row.obstacle_type,ols_surface_id=x.OLS_SURFACE_ID,surface_name=row.surface_eng or row.surface_aze,surface_type=row.surface_type,surface_elevation_m=x.SURFACE_ELEVATION_M,obstacle_top_elevation_m=x.OBSTACLE_TOP_ELEVATION_M,penetration_m=x.PENETRATION_M,status_id=x.STATUS_ID,status=row.status_name,created_date=x.CREATED_DATE,last_checked_date=x.LAST_CHECKED_DATE)
    @staticmethod
    def points(value):
        found=[]
        def walk(v):
            if isinstance(v,list) and len(v)>=3 and all(isinstance(n,(int,float)) for n in v[:3]): found.append((float(v[0]),float(v[1]),float(v[2])))
            elif isinstance(v,list):
                for child in v: walk(child)
        walk(value); return list(dict.fromkeys(found))
    @classmethod
    def elevation(cls,geojson,x,y):
        pts=cls.points(json.loads(geojson).get("coordinates",[]))
        if not pts: raise ViolationValidationError("OLS surface has no Z coordinates")
        if max(p[2] for p in pts)-min(p[2] for p in pts)<1e-9: return pts[0][2]
        lat_scale=111320.0; lon_scale=lat_scale*math.cos(math.radians(y))
        nearest=sorted(pts,key=lambda p:((p[0]-x)*lon_scale)**2+((p[1]-y)*lat_scale)**2)[:12]
        for p1,p2,p3 in combinations(nearest,3):
            x1,y1=(p1[0]-x)*lon_scale,(p1[1]-y)*lat_scale; x2,y2=(p2[0]-x)*lon_scale,(p2[1]-y)*lat_scale; x3,y3=(p3[0]-x)*lon_scale,(p3[1]-y)*lat_scale
            det=x1*(y2-y3)+x2*(y3-y1)+x3*(y1-y2)
            if abs(det)>1e-6:
                a=(p1[2]*(y2-y3)+p2[2]*(y3-y1)+p3[2]*(y1-y2))/det; b=(p1[2]*(x3-x2)+p2[2]*(x1-x3)+p3[2]*(x2-x1))/det; c=(p1[2]*(x2*y3-x3*y2)+p2[2]*(x3*y1-x1*y3)+p3[2]*(x1*y2-x2*y1))/det
                return c
        return sum(p[2] for p in nearest)/len(nearest)
    async def get(self,id):
        row=await self.repo.row(id)
        if not row: raise ViolationNotFoundError("Violation does not exist")
        return self.out(row)
    async def list(self,page,size,**filters):
        rows,total=await self.repo.list(offset=(page-1)*size,limit=size,**filters); return ViolationListResponse(items=[self.out(r) for r in rows],total=total,page=page,page_size=size)
    async def analyze(self,obstacle_id):
        obstacle=await self.repo.obstacle(obstacle_id)
        if not obstacle: raise ViolationNotFoundError("Obstacle does not exist")
        top=obstacle.TOP_ELEVATION_M
        if top is None and obstacle.GROUND_ELEVATION_M is not None and obstacle.OBJECT_HEIGHT_M is not None: top=obstacle.GROUND_ELEVATION_M+obstacle.OBJECT_HEIGHT_M
        if top is None: raise ViolationValidationError("Absolute top elevation cannot be calculated without ground elevation, DTM sampling, or supplied top elevation")
        active=await self.repo.named_status("active")
        if not active: raise ViolationValidationError("Active status is not configured")
        candidates=await self.repo.candidate_surfaces(obstacle,active.STATUS_ID); values=[]
        for row in candidates:
            z=Decimal(str(round(self.elevation(row.surface_geojson,float(row.x),float(row.y)),3))); penetration=Decimal(top)-z
            if penetration>0: values.append({"OBSTACLE_ID":obstacle_id,"OLS_SURFACE_ID":row[0].OLS_SURFACE_ID,"SURFACE_ELEVATION_M":z,"OBSTACLE_TOP_ELEVATION_M":top,"PENETRATION_M":penetration,"STATUS_ID":active.STATUS_ID})
        await self.repo.replace(obstacle_id,values); await self.session.commit()
        rows,_=await self.repo.list(obstacle_id=obstacle_id,offset=0,limit=1000)
        violations=[self.out(r) for r in rows]
        # A linked DTM is provenance metadata, not proof that this run sampled
        # the raster. Keep this false until the raster sampling adapter is used.
        return ObstacleAnalysisResponse(obstacle_id=obstacle_id,dtm_used=False,ground_elevation_m=obstacle.GROUND_ELEVATION_M,object_height_m=obstacle.OBJECT_HEIGHT_M,top_elevation_m=top,checked_surface_count=len(candidates),has_violation=bool(violations),violations=violations)
    async def manual_check(self,payload):
        airport=await self.repo.airport(payload.air_id)
        if not airport: raise ViolationNotFoundError("Airport does not exist")
        if not await self.session.get(ObstacleType,payload.obstacle_type_id): raise ViolationValidationError("Obstacle type does not exist")
        geometry=payload.geometry.model_dump(); lon,lat=await self.repo.representative_point(geometry)
        ground=payload.ground_elevation_m; top=payload.top_elevation_m; height=payload.object_height_m; dtm_id=None; dtm_used=False; sampling_message=None
        active=await self.repo.named_status("active")
        if not active: raise ViolationValidationError("Active status is not configured")
        if ground is None and top is None:
            dtm=await DtmRepository(self.session).applicable_model(payload.air_id,active.STATUS_ID,float(lon),float(lat))
            if dtm:
                try:
                    sample=await DtmSampler().sample(dtm,float(lon),float(lat)); ground=Decimal(str(sample.elevation_m)); dtm_id=sample.dtm_id; dtm_used=True
                except DtmSamplingError as exc: sampling_message=str(exc)
        if ground is not None and height is not None:
            calculated=ground+height
            if top is not None and abs(top-calculated)>Decimal("0.001"): raise ViolationValidationError("top_elevation_m must equal ground_elevation_m + object_height_m")
            top=calculated
        if top is None:
            return ManualObstacleCheckResponse(obstacle_id=None,analyzable=False,message=sampling_message or "Absolute top elevation cannot be calculated without ground elevation, a readable DTM, or supplied top elevation",dtm_used=dtm_used,dtm_id=dtm_id,ground_elevation_m=ground,object_height_m=height,top_elevation_m=None,checked_surface_count=0,has_violation=False,violations=[])
        candidates=await self.repo.candidate_surfaces_for_geometry(payload.air_id,geometry,active.STATUS_ID); results=[]
        for row in candidates:
            z=Decimal(str(round(self.elevation(row.surface_geojson,float(row.x),float(row.y)),3))); penetration=top-z
            if penetration>0: results.append(SurfaceCheckResult(ols_surface_id=row[0].OLS_SURFACE_ID,surface_name=row.surface_name,surface_type=row.surface_type,surface_elevation_m=z,penetration_m=penetration))
        obstacle_id=None
        if payload.persist:
            obstacle=Obstacle(AIR_ID=payload.air_id,DTM_ID=dtm_id,AZE_NAME=payload.aze_name,ENG_NAME=payload.eng_name,OBSTACLE_TYPE_ID=payload.obstacle_type_id,GROUND_ELEVATION_M=ground,OBJECT_HEIGHT_M=height,TOP_ELEVATION_M=top,GEOM=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)),4326),STATUS_ID=active.STATUS_ID)
            self.session.add(obstacle); await self.session.flush(); obstacle_id=obstacle.OBSTACLE_ID
            values=[{"OBSTACLE_ID":obstacle_id,"OLS_SURFACE_ID":v.ols_surface_id,"SURFACE_ELEVATION_M":v.surface_elevation_m,"OBSTACLE_TOP_ELEVATION_M":top,"PENETRATION_M":v.penetration_m,"STATUS_ID":active.STATUS_ID} for v in results]
            await self.repo.replace(obstacle_id,values); await self.session.commit()
        return ManualObstacleCheckResponse(obstacle_id=obstacle_id,analyzable=True,dtm_used=dtm_used,dtm_id=dtm_id,ground_elevation_m=ground,object_height_m=height,top_elevation_m=top,checked_surface_count=len(candidates),has_violation=bool(results),violations=results)
    async def status(self,id,status_id):
        x=await self.repo.violation(id)
        if not x: raise ViolationNotFoundError("Violation does not exist")
        if not await self.repo.status(status_id): raise ViolationValidationError("Status does not exist")
        x.STATUS_ID=status_id; await self.session.commit()
    async def summary(self,air_id):
        if not await self.repo.airport(air_id): raise ViolationNotFoundError("Airport does not exist")
        rows,total=await self.repo.list(air_id=air_id,offset=0,limit=100000); items=[self.out(r) for r in rows]
        def counts(field):
            out={}
            for i in items: out[str(getattr(i,field))]=out.get(str(getattr(i,field)),0)+1
            return out
        return ViolationSummary(air_id=air_id,total_violations=total,affected_obstacles=len({i.obstacle_id for i in items}),maximum_penetration_m=max((i.penetration_m for i in items),default=None),by_surface_type=counts("surface_type"),by_obstacle_type=counts("obstacle_type"),by_status=counts("status"))
