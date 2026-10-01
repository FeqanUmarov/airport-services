import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.dtm.models import DtmSource
from app.modules.dtm.repository import DtmRepository
from app.modules.dtm.schemas import DtmListResponse,DtmResponse
class DtmNotFoundError(ValueError): pass
class DtmValidationError(ValueError): pass
class DtmService:
    def __init__(self,session:AsyncSession): self.session=session; self.repo=DtmRepository(session)
    @staticmethod
    def out(row):
        x=row[0]; return DtmResponse(dtm_id=x.DTM_ID,air_id=x.AIR_ID,airport_name=row.airport_name,name=x.NAME,source_path=x.SOURCE_PATH,source_type=x.SOURCE_TYPE,crs=x.CRS,resolution_m=x.RESOLUTION_M,nodata_value=x.NODATA_VALUE,coverage_geom=json.loads(row.coverage_geojson) if row.coverage_geojson else None,is_primary=x.IS_PRIMARY,status_id=x.STATUS_ID,status=row.status_name,created_date=x.CREATED_DATE,last_edited_date=x.LAST_EDITED_DATE)
    async def get(self,id):
        row=await self.repo.row(id)
        if not row: raise DtmNotFoundError("DTM source does not exist")
        return self.out(row)
    async def list(self,air_id,page,size,search,status_id):
        if not await self.repo.airport(air_id): raise DtmNotFoundError("Airport does not exist")
        rows,total=await self.repo.list(air_id,(page-1)*size,size,search,status_id); return DtmListResponse(items=[self.out(r) for r in rows],total=total,page=page,page_size=size)
    async def active(self,air_id):
        if not await self.repo.airport(air_id): raise DtmNotFoundError("Airport does not exist")
        status=await self.repo.named_status("active")
        row=await self.repo.active(air_id,status.STATUS_ID) if status else None
        if not row: raise DtmNotFoundError("Active DTM source does not exist for this airport")
        return self.out(row)
    async def create(self,air_id,p):
        if not await self.repo.airport(air_id): raise DtmNotFoundError("Airport does not exist")
        status=await self.repo.named_status("active")
        if not status: raise DtmValidationError("Active status is not configured")
        if p.is_primary: await self.repo.clear_primary(air_id)
        x=DtmSource(AIR_ID=air_id,NAME=p.name,SOURCE_PATH=p.source_path,SOURCE_TYPE=p.source_type,CRS=p.crs,RESOLUTION_M=p.resolution_m,NODATA_VALUE=p.nodata_value,COVERAGE_GEOM=self.repo.geom(p.coverage_geom.model_dump()) if p.coverage_geom else None,IS_PRIMARY=p.is_primary,STATUS_ID=status.STATUS_ID)
        self.session.add(x); await self.session.commit(); return await self.get(x.DTM_ID)
    async def update(self,id,c):
        x=await self.repo.model(id)
        if not x: raise DtmNotFoundError("DTM source does not exist")
        if c.get("is_primary") is True: await self.repo.clear_primary(x.AIR_ID,id)
        for a,b in {"name":"NAME","source_path":"SOURCE_PATH","source_type":"SOURCE_TYPE","crs":"CRS","resolution_m":"RESOLUTION_M","nodata_value":"NODATA_VALUE","is_primary":"IS_PRIMARY"}.items():
            if a in c: setattr(x,b,c[a])
        if "coverage_geom" in c: x.COVERAGE_GEOM=self.repo.geom(c["coverage_geom"]) if c["coverage_geom"] else None
        await self.session.commit(); return await self.get(id)
    async def status(self,id,status_id):
        x=await self.repo.model(id)
        if not x: raise DtmNotFoundError("DTM source does not exist")
        if not await self.repo.status(status_id): raise DtmValidationError("Status does not exist")
        x.STATUS_ID=status_id; await self.session.commit()
    async def archive(self,id):
        x=await self.repo.model(id)
        if not x: raise DtmNotFoundError("DTM source does not exist")
        s=await self.repo.named_status("archived")
        if not s: raise DtmValidationError("Archived status is not configured")
        x.STATUS_ID=s.STATUS_ID; x.IS_PRIMARY=False; await self.session.commit()
