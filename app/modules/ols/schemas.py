from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AutomaticOlsGenerationRequest(BaseModel):
    standard_id: int = Field(gt=0)
    run_id: int = Field(gt=0)
    replace_existing: bool = True
    revision_note: str | None = Field(default=None, max_length=500)


class GeneratedOlsSurface(BaseModel):
    ols_surface_id: int
    standard_ols_id: int
    surface_type: str
    run_id: int
    run_dir_id: int | None
    generation_method: str
    reference_geometry: str | None = None
    topology_status: Literal["PASSED", "WARNING", "NOT_APPLICABLE"] = "NOT_APPLICABLE"
    topology_message: str | None = None
    gap_m: float | None = None
    overlap_m: float | None = None


class AutomaticOlsGenerationResponse(BaseModel):
    air_id: int
    run_id: int
    standard_id: int
    generated_count: int
    surfaces: list[GeneratedOlsSurface]


class ManualOlsGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def not_empty(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("Geometry coordinates cannot be empty")
        return value

    def coordinate_dimension(self) -> int:
        value: Any = self.coordinates
        while isinstance(value, list) and value and isinstance(value[0], list):
            value = value[0]
        return len(value) if isinstance(value, (list, tuple)) else 0


class ManualOlsCreate(BaseModel):
    standard_ols_id: int = Field(gt=0)
    air_id: int = Field(gt=0)
    run_id: int | None = Field(default=None, gt=0)
    run_dir_id: int | None = Field(default=None, gt=0)
    aze_name: str | None = Field(default=None, max_length=255)
    eng_name: str | None = Field(default=None, max_length=255)
    geometry: ManualOlsGeometry
    default_elevation_m: Decimal | None = None
    revision_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_geometry_and_links(self) -> "ManualOlsCreate":
        if self.run_dir_id is not None and self.run_id is None:
            raise ValueError("run_id is required when run_dir_id is supplied")
        if self.geometry.coordinate_dimension() == 2 and self.default_elevation_m is None:
            raise ValueError("default_elevation_m is required for 2D geometry")
        return self


class ManualOlsUpdate(BaseModel):
    standard_ols_id: int | None = Field(default=None, gt=0)
    run_id: int | None = Field(default=None, gt=0)
    run_dir_id: int | None = Field(default=None, gt=0)
    aze_name: str | None = Field(default=None, max_length=255)
    eng_name: str | None = Field(default=None, max_length=255)
    geometry: ManualOlsGeometry | None = None
    default_elevation_m: Decimal | None = None
    revision_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_update(self) -> "ManualOlsUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        if self.geometry and self.geometry.coordinate_dimension() == 2 and self.default_elevation_m is None:
            raise ValueError("default_elevation_m is required for 2D geometry")
        return self


class OlsSurfaceStatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class OlsSurfaceResponse(BaseModel):
    ols_surface_id: int
    standard_ols_id: int
    standard_id: int
    standard_code: str
    surface_type: str
    generation_method_id: int
    generation_method: str
    air_id: int
    run_id: int | None
    run_dir_id: int | None
    aze_name: str | None
    eng_name: str | None
    geometry: dict[str, Any]
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class OlsSurfaceListResponse(BaseModel):
    items: list[OlsSurfaceResponse]
    total: int
    page: int
    page_size: int


class OlsSurfaceSummary(BaseModel):
    air_id: int
    total: int
    by_surface_type: dict[str, int]
    by_generation_method: dict[str, int]
    by_status: dict[str, int]
