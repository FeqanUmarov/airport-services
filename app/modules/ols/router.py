from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, EditorUser
from app.modules.ols.schemas import AutomaticOlsGenerationRequest, AutomaticOlsGenerationResponse, ManualOlsCreate, ManualOlsUpdate, OlsSurfaceListResponse, OlsSurfaceResponse, OlsSurfaceStatusUpdate, OlsSurfaceSummary
from app.modules.ols.service import AutomaticOlsService, ManualOlsService, OlsNotFoundError, OlsValidationError


router = APIRouter(prefix="/ols", tags=["ols"])
data_router = APIRouter(tags=["ols-data"])


@router.post("/generate", response_model=AutomaticOlsGenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_ols(payload: AutomaticOlsGenerationRequest, editor: EditorUser, session: DatabaseSession) -> AutomaticOlsGenerationResponse:
    try:
        return await AutomaticOlsService(session).generate(payload.standard_id, payload.run_id, payload.replace_existing, editor.user.USER_ID, payload.revision_note)
    except OlsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OlsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def ols_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(exc,OlsNotFoundError) else 400,detail=str(exc))


@data_router.get("/airports/{air_id}/ols-surfaces",response_model=OlsSurfaceListResponse)
async def canonical_ols_list(air_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),run_id:int|None=Query(default=None,gt=0),run_dir_id:int|None=Query(default=None,gt=0),standard_id:int|None=Query(default=None,gt=0),surface_type:str|None=None,generation_method:str|None=None,status_id:int|None=Query(default=None,gt=0)) -> OlsSurfaceListResponse:
    del current
    try: return await ManualOlsService(session).list_surfaces(air_id=air_id,page=page,page_size=page_size,run_id=run_id,run_dir_id=run_dir_id,standard_id=standard_id,surface_type=surface_type,generation_method=generation_method,status_id=status_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@data_router.get("/airports/{air_id}/ols-surfaces/geojson")
async def ols_geojson(air_id:int,current:CurrentUser,session:DatabaseSession,run_id:int|None=Query(default=None,gt=0),run_dir_id:int|None=Query(default=None,gt=0),standard_id:int|None=Query(default=None,gt=0),surface_type:str|None=None,generation_method:str|None=None,status_id:int|None=Query(default=None,gt=0)) -> dict:
    del current
    try: return await ManualOlsService(session).feature_collection(air_id=air_id,run_id=run_id,run_dir_id=run_dir_id,standard_id=standard_id,surface_type=surface_type,generation_method=generation_method,status_id=status_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@data_router.get("/airports/{air_id}/ols-surfaces/summary",response_model=OlsSurfaceSummary)
async def ols_summary(air_id:int,current:CurrentUser,session:DatabaseSession) -> OlsSurfaceSummary:
    del current
    try: return await ManualOlsService(session).summary(air_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@data_router.get("/ols-surfaces/{surface_id}",response_model=OlsSurfaceResponse)
async def canonical_ols_detail(surface_id:int,current:CurrentUser,session:DatabaseSession) -> OlsSurfaceResponse:
    del current
    try: return await ManualOlsService(session).get(surface_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@router.get("/airports/{air_id}/surfaces",response_model=OlsSurfaceListResponse)
async def list_ols_surfaces(air_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),run_id:int|None=Query(default=None,gt=0),run_dir_id:int|None=Query(default=None,gt=0),generation_method:str|None=None,status_id:int|None=Query(default=None,gt=0)) -> OlsSurfaceListResponse:
    del current
    try: return await ManualOlsService(session).list_surfaces(air_id=air_id,page=page,page_size=page_size,run_id=run_id,run_dir_id=run_dir_id,generation_method=generation_method,status_id=status_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@router.post("/manual",response_model=OlsSurfaceResponse,status_code=201)
async def create_manual_ols(payload:ManualOlsCreate,editor:EditorUser,session:DatabaseSession) -> OlsSurfaceResponse:
    try: return await ManualOlsService(session).create(payload,editor.user.USER_ID)
    except (OlsNotFoundError,OlsValidationError) as exc: raise ols_error(exc) from exc


@router.get("/surfaces/{surface_id}",response_model=OlsSurfaceResponse)
async def get_ols_surface(surface_id:int,current:CurrentUser,session:DatabaseSession) -> OlsSurfaceResponse:
    del current
    try: return await ManualOlsService(session).get(surface_id)
    except OlsNotFoundError as exc: raise ols_error(exc) from exc


@router.patch("/surfaces/{surface_id}",response_model=OlsSurfaceResponse)
async def update_manual_ols(surface_id:int,payload:ManualOlsUpdate,editor:EditorUser,session:DatabaseSession) -> OlsSurfaceResponse:
    changes=payload.model_dump(exclude_unset=True)
    if changes.get("geometry") is not None and hasattr(changes["geometry"], "model_dump"):
        changes["geometry"] = changes["geometry"].model_dump()
    try: return await ManualOlsService(session).update(surface_id,changes,editor.user.USER_ID)
    except (OlsNotFoundError,OlsValidationError) as exc: raise ols_error(exc) from exc


@router.patch("/surfaces/{surface_id}/status",status_code=204)
async def update_ols_status(surface_id:int,payload:OlsSurfaceStatusUpdate,editor:EditorUser,session:DatabaseSession) -> Response:
    try: await ManualOlsService(session).update_status(surface_id,payload.status_id,editor.user.USER_ID)
    except (OlsNotFoundError,OlsValidationError) as exc: raise ols_error(exc) from exc
    return Response(status_code=204)


@router.delete("/surfaces/{surface_id}",status_code=204)
async def archive_ols_surface(surface_id:int,admin:AdminUser,session:DatabaseSession) -> Response:
    try: await ManualOlsService(session).archive(surface_id,admin.user.USER_ID)
    except (OlsNotFoundError,OlsValidationError) as exc: raise ols_error(exc) from exc
    return Response(status_code=204)
