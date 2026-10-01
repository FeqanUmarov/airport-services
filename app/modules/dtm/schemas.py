from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.modules.airports.schemas import BoundaryGeometry

SourceType = Literal["GEOTIFF", "COG", "WCS", "OTHER"]

class DtmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_path: str = Field(min_length=1, max_length=500)
    source_type: SourceType = "GEOTIFF"
    crs: str | None = Field(default=None, max_length=50)
    resolution_m: Decimal | None = Field(default=None, gt=0)
    nodata_value: Decimal | None = None
    coverage_geom: BoundaryGeometry | None = None
    is_primary: bool = False
    @model_validator(mode="after")
    def valid(self):
        self.name=self.name.strip(); self.source_path=self.source_path.strip()
        if self.coverage_geom and self.coverage_geom.type not in {"Polygon","MultiPolygon"}: raise ValueError("coverage_geom must be Polygon or MultiPolygon")
        return self

class DtmUpdate(BaseModel):
    name: str | None = Field(default=None,min_length=1,max_length=255)
    source_path: str | None = Field(default=None,min_length=1,max_length=500)
    source_type: SourceType | None = None
    crs: str | None = Field(default=None,max_length=50)
    resolution_m: Decimal | None = Field(default=None,gt=0)
    nodata_value: Decimal | None = None
    coverage_geom: BoundaryGeometry | None = None
    is_primary: bool | None = None
    @model_validator(mode="after")
    def valid(self):
        if not self.model_fields_set: raise ValueError("At least one field must be supplied")
        if self.coverage_geom and self.coverage_geom.type not in {"Polygon","MultiPolygon"}: raise ValueError("coverage_geom must be Polygon or MultiPolygon")
        return self

class DtmStatusUpdate(BaseModel): status_id: int = Field(gt=0)
class DtmResponse(BaseModel):
    dtm_id:int; air_id:int; airport_name:str; name:str; source_path:str|None; source_type:str; crs:str|None
    resolution_m:Decimal|None; nodata_value:Decimal|None; coverage_geom:dict|None; is_primary:bool
    status_id:int; status:str; created_date:datetime; last_edited_date:datetime
class DtmListResponse(BaseModel): items:list[DtmResponse]; total:int; page:int; page_size:int
class DtmSampleRequest(BaseModel):
    longitude:float=Field(ge=-180,le=180); latitude:float=Field(ge=-90,le=90)
class DtmSampleResponse(BaseModel):
    dtm_id:int; longitude:float; latitude:float; elevation_m:Decimal
