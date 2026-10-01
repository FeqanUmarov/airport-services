import csv,io
from fastapi import APIRouter,HTTPException,Query,Response,status
from app.core.dependencies import CurrentUser,DatabaseSession,EditorUser
from app.modules.violations.schemas import ManualObstacleCheckRequest,ManualObstacleCheckResponse,ObstacleAnalysisResponse,ViolationListResponse,ViolationResponse,ViolationStatusUpdate,ViolationSummary
from app.modules.violations.service import ViolationNotFoundError,ViolationService,ViolationValidationError
router=APIRouter(tags=["violations and reports"])
def error(e): return HTTPException(status_code=404 if isinstance(e,ViolationNotFoundError) else 400,detail=str(e))
@router.post("/obstacles/check",response_model=ManualObstacleCheckResponse)
async def manual_check(payload:ManualObstacleCheckRequest,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await ViolationService(session).manual_check(payload)
    except (ViolationNotFoundError,ViolationValidationError) as e: raise error(e) from e
@router.post("/obstacles/{obstacle_id}/analyze",response_model=ObstacleAnalysisResponse)
async def analyze(obstacle_id:int,editor:EditorUser,session:DatabaseSession):
    del editor
    try: return await ViolationService(session).analyze(obstacle_id)
    except (ViolationNotFoundError,ViolationValidationError) as e: raise error(e) from e
@router.get("/obstacles/{obstacle_id}/violations",response_model=ViolationListResponse)
async def obstacle_violations(obstacle_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),status_id:int|None=Query(None,gt=0)):
    del current
    if not await ViolationService(session).repo.obstacle(obstacle_id): raise HTTPException(404,"Obstacle does not exist")
    return await ViolationService(session).list(page,page_size,obstacle_id=obstacle_id,status_id=status_id)
@router.get("/airports/{air_id}/violations",response_model=ViolationListResponse)
async def airport_violations(air_id:int,current:CurrentUser,session:DatabaseSession,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),status_id:int|None=Query(None,gt=0),surface_type:str|None=None):
    del current
    service=ViolationService(session)
    if not await service.repo.airport(air_id): raise HTTPException(404,"Airport does not exist")
    return await service.list(page,page_size,air_id=air_id,status_id=status_id,surface_type=surface_type)
@router.get("/violations/{violation_id}",response_model=ViolationResponse)
async def get_violation(violation_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await ViolationService(session).get(violation_id)
    except ViolationNotFoundError as e: raise error(e) from e
@router.patch("/violations/{violation_id}/status",status_code=204)
async def status_violation(violation_id:int,payload:ViolationStatusUpdate,editor:EditorUser,session:DatabaseSession):
    del editor
    try: await ViolationService(session).status(violation_id,payload.status_id)
    except (ViolationNotFoundError,ViolationValidationError) as e: raise error(e) from e
    return Response(status_code=204)
@router.get("/airports/{air_id}/reports/violations/summary",response_model=ViolationSummary)
async def summary(air_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await ViolationService(session).summary(air_id)
    except ViolationNotFoundError as e: raise error(e) from e
@router.get("/airports/{air_id}/reports/violations.csv")
async def csv_report(air_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    service=ViolationService(session)
    if not await service.repo.airport(air_id): raise HTTPException(404,"Airport does not exist")
    rows,_=await service.repo.list(air_id=air_id,offset=0,limit=100000); output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["violation_id","obstacle_id","obstacle_name","obstacle_type","ols_surface_id","surface_name","surface_type","surface_elevation_m","obstacle_top_elevation_m","penetration_m","status","last_checked_date"])
    for row in rows:
        x=service.out(row); writer.writerow([x.violation_id,x.obstacle_id,x.obstacle_name,x.obstacle_type,x.ols_surface_id,x.surface_name,x.surface_type,x.surface_elevation_m,x.obstacle_top_elevation_m,x.penetration_m,x.status,x.last_checked_date.isoformat()])
    return Response(content=output.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="airport-{air_id}-violations.csv"'})
