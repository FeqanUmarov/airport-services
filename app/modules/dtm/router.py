from fastapi import APIRouter,HTTPException,Query,Response,status
from app.core.dependencies import AdminUser,CurrentUser,DatabaseSession,EditorUser
from app.modules.dtm.schemas import DtmCreate,DtmListResponse,DtmResponse,DtmSampleRequest,DtmSampleResponse,DtmStatusUpdate,DtmUpdate
from app.modules.dtm.service import DtmNotFoundError,DtmService,DtmValidationError
from app.modules.dtm.sampler import DtmSampler,DtmSamplingError
router=APIRouter(tags=["dtm"])
def error(e): return HTTPException(status_code=404 if isinstance(e,DtmNotFoundError) else 400,detail=str(e))
@router.get("/airports/{air_id}/dtm-sources",response_model=DtmListResponse)
async def list_dtm(air_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_id:int|None=Query(None,gt=0)):
    del current
    try: return await DtmService(session).list(air_id,page,page_size,search,status_id)
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
@router.get("/airports/{air_id}/dtm-sources/active",response_model=DtmResponse)
async def active_dtm(air_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await DtmService(session).active(air_id)
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
@router.post("/airports/{air_id}/dtm-sources",response_model=DtmResponse,status_code=201)
async def create_dtm(air_id:int,payload:DtmCreate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await DtmService(session).create(air_id,payload)
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
@router.get("/dtm-sources/{dtm_id}",response_model=DtmResponse)
async def get_dtm(dtm_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await DtmService(session).get(dtm_id)
    except DtmNotFoundError as e: raise error(e) from e
@router.post("/dtm-sources/{dtm_id}/sample",response_model=DtmSampleResponse)
async def sample_dtm(dtm_id:int,payload:DtmSampleRequest,current:CurrentUser,session:DatabaseSession):
    del current
    source=await DtmService(session).repo.model(dtm_id)
    if source is None: raise HTTPException(404,"DTM source does not exist")
    try: sample=await DtmSampler().sample(source,payload.longitude,payload.latitude)
    except DtmSamplingError as exc: raise HTTPException(400,str(exc)) from exc
    return DtmSampleResponse(dtm_id=sample.dtm_id,longitude=payload.longitude,latitude=payload.latitude,elevation_m=sample.elevation_m)
@router.patch("/dtm-sources/{dtm_id}",response_model=DtmResponse)
async def update_dtm(dtm_id:int,payload:DtmUpdate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await DtmService(session).update(dtm_id,payload.model_dump(exclude_unset=True,mode="json"))
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
@router.patch("/dtm-sources/{dtm_id}/status",status_code=204)
async def status_dtm(dtm_id:int,payload:DtmStatusUpdate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: await DtmService(session).status(dtm_id,payload.status_id)
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
    return Response(status_code=204)
@router.delete("/dtm-sources/{dtm_id}",status_code=204)
async def archive_dtm(dtm_id:int,admin:AdminUser,session:DatabaseSession):
    del admin
    try: await DtmService(session).archive(dtm_id)
    except (DtmNotFoundError,DtmValidationError) as e: raise error(e) from e
    return Response(status_code=204)
