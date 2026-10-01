from fastapi import APIRouter,File,Form,HTTPException,Query,Response,UploadFile,status
from app.core.dependencies import AdminUser,CurrentUser,DatabaseSession,EditorUser
from app.modules.obstacles.schemas import ObstacleCreate,ObstacleGeoJsonResponse,ObstacleListResponse,ObstacleResponse,ObstacleStatusUpdate,ObstacleUpdate
from app.modules.obstacles.service import ObstacleNotFoundError,ObstacleService,ObstacleValidationError
from app.modules.obstacles.importer import ShapefileImporter,ShapefileImportError
from app.modules.violations.service import ViolationService
from app.modules.violations.schemas import ObstacleImportResponse
router=APIRouter(tags=["obstacles"])
def error(e): return HTTPException(status_code=404 if isinstance(e,ObstacleNotFoundError) else 400,detail=str(e))
@router.post("/obstacles/import",response_model=ObstacleImportResponse)
async def import_obstacles(editor:EditorUser,session:DatabaseSession,file:UploadFile=File(...),air_id:int=Form(...,gt=0),obstacle_type_id:int=Form(...,gt=0),name_field:str|None=Form(None),ground_field:str|None=Form(None),height_field:str|None=Form(None),top_field:str|None=Form(None),default_height_m:float|None=Form(None,ge=0)):
    del editor
    if not file.filename or not file.filename.lower().endswith(".zip"): raise HTTPException(400,"A ZIP Shapefile archive is required")
    content=await file.read(__import__("app.core.config",fromlist=["settings"]).settings.import_max_bytes+1)
    try: return await ShapefileImporter(ViolationService(session)).run(content,air_id=air_id,obstacle_type_id=obstacle_type_id,name_field=name_field,ground_field=ground_field,height_field=height_field,top_field=top_field,default_height=default_height_m)
    except ShapefileImportError as exc: raise HTTPException(400,str(exc)) from exc
@router.get("/airports/{air_id}/obstacles",response_model=ObstacleListResponse)
async def list_obstacles(air_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,obstacle_type_id:int|None=Query(None,gt=0),status_id:int|None=Query(None,gt=0)):
    del current
    try: return await ObstacleService(session).list(air_id,page,page_size,search,obstacle_type_id,status_id)
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
@router.get("/airports/{air_id}/obstacles/geojson",response_model=ObstacleGeoJsonResponse)
async def obstacles_geojson(air_id:int,current:CurrentUser,session:DatabaseSession,status_id:int|None=Query(None,gt=0)):
    del current
    try: return await ObstacleService(session).geojson(air_id,status_id)
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
@router.post("/airports/{air_id}/obstacles",response_model=ObstacleResponse,status_code=201)
async def create_obstacle(air_id:int,payload:ObstacleCreate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await ObstacleService(session).create(air_id,payload)
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
@router.get("/obstacles/{obstacle_id}",response_model=ObstacleResponse)
async def get_obstacle(obstacle_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await ObstacleService(session).get(obstacle_id)
    except ObstacleNotFoundError as e: raise error(e) from e
@router.patch("/obstacles/{obstacle_id}",response_model=ObstacleResponse)
async def update_obstacle(obstacle_id:int,payload:ObstacleUpdate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await ObstacleService(session).update(obstacle_id,payload.model_dump(exclude_unset=True,mode="json"))
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
@router.patch("/obstacles/{obstacle_id}/status",status_code=204)
async def status_obstacle(obstacle_id:int,payload:ObstacleStatusUpdate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: await ObstacleService(session).status(obstacle_id,payload.status_id)
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
    return Response(status_code=204)
@router.delete("/obstacles/{obstacle_id}",status_code=204)
async def archive_obstacle(obstacle_id:int,admin:AdminUser,session:DatabaseSession):
    del admin
    try: await ObstacleService(session).archive(obstacle_id)
    except (ObstacleNotFoundError,ObstacleValidationError) as e: raise error(e) from e
    return Response(status_code=204)
