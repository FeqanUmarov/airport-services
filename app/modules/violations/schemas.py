from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel,Field
from app.modules.obstacles.schemas import ObstacleGeometry

class ViolationStatusUpdate(BaseModel): status_id:int=Field(gt=0)
class ViolationResponse(BaseModel):
    violation_id:int; obstacle_id:int; obstacle_name:str|None; obstacle_type:str
    ols_surface_id:int; surface_name:str|None; surface_type:str
    surface_elevation_m:Decimal; obstacle_top_elevation_m:Decimal; penetration_m:Decimal
    status_id:int; status:str; created_date:datetime; last_checked_date:datetime
class ViolationListResponse(BaseModel): items:list[ViolationResponse]; total:int; page:int; page_size:int
class ObstacleAnalysisResponse(BaseModel):
    obstacle_id:int; dtm_used:bool; ground_elevation_m:Decimal|None; object_height_m:Decimal|None
    top_elevation_m:Decimal; checked_surface_count:int; has_violation:bool; violations:list[ViolationResponse]
class ViolationSummary(BaseModel):
    air_id:int; total_violations:int; affected_obstacles:int; maximum_penetration_m:Decimal|None
    by_surface_type:dict[str,int]; by_obstacle_type:dict[str,int]; by_status:dict[str,int]
class ManualObstacleCheckRequest(BaseModel):
    air_id:int=Field(gt=0); obstacle_type_id:int=Field(gt=0); geometry:ObstacleGeometry
    aze_name:str|None=Field(default=None,max_length=255); eng_name:str|None=Field(default=None,max_length=255)
    object_height_m:Decimal|None=Field(default=None,ge=0); ground_elevation_m:Decimal|None=None; top_elevation_m:Decimal|None=None
    persist:bool=False
class SurfaceCheckResult(BaseModel):
    ols_surface_id:int; surface_name:str|None; surface_type:str; surface_elevation_m:Decimal; penetration_m:Decimal
class ManualObstacleCheckResponse(BaseModel):
    obstacle_id:int|None; analyzable:bool; message:str|None=None; dtm_used:bool; dtm_id:int|None=None
    ground_elevation_m:Decimal|None; object_height_m:Decimal|None; top_elevation_m:Decimal|None
    checked_surface_count:int; has_violation:bool; violations:list[SurfaceCheckResult]
class ObstacleImportItem(BaseModel): feature_index:int; success:bool; obstacle_id:int|None=None; has_violation:bool=False; violation_count:int=0; error:str|None=None
class ObstacleImportResponse(BaseModel): imported_count:int; failed_count:int; items:list[ObstacleImportItem]
