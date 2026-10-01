from datetime import datetime
from decimal import Decimal
from typing import Any,Literal
from pydantic import BaseModel,Field,field_validator,model_validator

class ObstacleGeometry(BaseModel):
    type: Literal["Point","LineString","Polygon","MultiPoint","MultiLineString","MultiPolygon"]
    coordinates: list[Any]
    @field_validator("coordinates")
    @classmethod
    def nonempty(cls,v):
        if not v: raise ValueError("Geometry coordinates cannot be empty")
        return v

class ObstacleCreate(BaseModel):
    dtm_id:int|None=Field(default=None,gt=0)
    aze_name:str|None=Field(default=None,max_length=255)
    eng_name:str|None=Field(default=None,max_length=255)
    obstacle_type_id:int=Field(gt=0)
    ground_elevation_m:Decimal|None=None
    object_height_m:Decimal|None=Field(default=None,ge=0)
    top_elevation_m:Decimal|None=None
    geometry:ObstacleGeometry
    @model_validator(mode="after")
    def elevations(self):
        if self.ground_elevation_m is None and self.top_elevation_m is None: raise ValueError("ground_elevation_m or top_elevation_m is required; terrain elevation is never invented")
        if self.ground_elevation_m is not None and self.object_height_m is not None:
            calculated=self.ground_elevation_m+self.object_height_m
            if self.top_elevation_m is not None and abs(self.top_elevation_m-calculated)>Decimal("0.001"): raise ValueError("top_elevation_m must equal ground_elevation_m + object_height_m")
            self.top_elevation_m=calculated
        return self

class ObstacleUpdate(BaseModel):
    dtm_id:int|None=Field(default=None,gt=0)
    aze_name:str|None=Field(default=None,max_length=255)
    eng_name:str|None=Field(default=None,max_length=255)
    obstacle_type_id:int|None=Field(default=None,gt=0)
    ground_elevation_m:Decimal|None=None
    object_height_m:Decimal|None=Field(default=None,ge=0)
    top_elevation_m:Decimal|None=None
    geometry:ObstacleGeometry|None=None
    @model_validator(mode="after")
    def has_fields(self):
        if not self.model_fields_set: raise ValueError("At least one field must be supplied")
        return self

class ObstacleStatusUpdate(BaseModel): status_id:int=Field(gt=0)
class ObstacleResponse(BaseModel):
    obstacle_id:int; air_id:int; airport_name:str; dtm_id:int|None; dtm_name:str|None
    aze_name:str|None; eng_name:str|None; obstacle_type_id:int; obstacle_type_code:str; obstacle_type_name:str|None
    ground_elevation_m:Decimal|None; object_height_m:Decimal|None; top_elevation_m:Decimal|None
    geometry:dict[str,Any]; status_id:int; status:str; created_date:datetime; last_edited_date:datetime
class ObstacleListResponse(BaseModel): items:list[ObstacleResponse]; total:int; page:int; page_size:int
class ObstacleGeoJsonResponse(BaseModel): type:Literal["FeatureCollection"]="FeatureCollection"; features:list[dict[str,Any]]
