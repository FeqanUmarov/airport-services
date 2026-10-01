from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.airports.schemas import PointGeometry


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def not_empty(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("Polygon coordinates cannot be empty")
        return value


class LineStringGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[tuple[float, float]] = Field(min_length=2)


class RunwayCreate(BaseModel):
    aze_name: str = Field(min_length=1, max_length=150)
    eng_name: str = Field(min_length=1, max_length=150)
    designator_1: str = Field(min_length=1, max_length=10)
    designator_2: str = Field(min_length=1, max_length=10)
    length_m: Decimal = Field(gt=0)
    width_m: Decimal = Field(gt=0)
    geom: PolygonGeometry
    centerline_geom: LineStringGeometry

    @field_validator("aze_name", "eng_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("designator_1", "designator_2")
    @classmethod
    def normalize_designator(cls, value: str) -> str:
        return value.strip().upper()


class RunwayUpdate(BaseModel):
    aze_name: str | None = Field(default=None, min_length=1, max_length=150)
    eng_name: str | None = Field(default=None, min_length=1, max_length=150)
    designator_1: str | None = Field(default=None, min_length=1, max_length=10)
    designator_2: str | None = Field(default=None, min_length=1, max_length=10)
    length_m: Decimal | None = Field(default=None, gt=0)
    width_m: Decimal | None = Field(default=None, gt=0)
    geom: PolygonGeometry | None = None
    centerline_geom: LineStringGeometry | None = None

    @field_validator("designator_1", "designator_2")
    @classmethod
    def normalize_designator(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @model_validator(mode="after")
    def has_value(self) -> "RunwayUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class StatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class RunwayResponse(BaseModel):
    run_id: int
    air_id: int
    airport_name: str
    aze_name: str
    eng_name: str
    designator_1: str
    designator_2: str
    length_m: Decimal
    width_m: Decimal
    geom: dict[str, Any]
    centerline_geom: dict[str, Any]
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class RunwayListResponse(BaseModel):
    items: list[RunwayResponse]
    total: int


class DirectionCreate(BaseModel):
    designator: str = Field(min_length=1, max_length=10)
    true_bearing_deg: Decimal = Field(ge=0, lt=360)
    threshold_elevation_m: Decimal
    threshold_geom: PointGeometry
    slope_pct: Decimal

    @field_validator("designator")
    @classmethod
    def normalize_designator(cls, value: str) -> str:
        return value.strip().upper()


class DirectionUpdate(BaseModel):
    designator: str | None = Field(default=None, min_length=1, max_length=10)
    true_bearing_deg: Decimal | None = Field(default=None, ge=0, lt=360)
    threshold_elevation_m: Decimal | None = None
    threshold_geom: PointGeometry | None = None
    slope_pct: Decimal | None = None

    @model_validator(mode="after")
    def has_value(self) -> "DirectionUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class DirectionResponse(BaseModel):
    run_dir_id: int
    run_id: int
    designator: str
    true_bearing_deg: Decimal
    threshold_elevation_m: Decimal
    threshold_geom: dict[str, Any]
    slope_pct: Decimal
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class StripUpsert(BaseModel):
    length_m: Decimal = Field(gt=0)
    width_m: Decimal = Field(gt=0)
    geom: PolygonGeometry


class StripGenerateRequest(BaseModel):
    length_m: Decimal = Field(gt=0)
    centerline_offset_m: Decimal = Field(gt=0)


class StripResponse(BaseModel):
    strip_id: int
    run_id: int
    length_m: Decimal
    width_m: Decimal
    geom: dict[str, Any]
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class AreaCreate(BaseModel):
    area_type_id: int = Field(gt=0)
    length_m: Decimal = Field(gt=0)
    width_m: Decimal = Field(gt=0)
    geom: PolygonGeometry


class ClearwayGenerateRequest(BaseModel):
    length_m: Decimal = Field(gt=0)
    width_m: Decimal | None = Field(default=None, gt=0)


class AreaUpdate(BaseModel):
    area_type_id: int | None = Field(default=None, gt=0)
    length_m: Decimal | None = Field(default=None, gt=0)
    width_m: Decimal | None = Field(default=None, gt=0)
    geom: PolygonGeometry | None = None

    @model_validator(mode="after")
    def has_value(self) -> "AreaUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class AreaResponse(BaseModel):
    runway_area_id: int
    run_id: int
    run_dir_id: int
    area_type_id: int
    area_type_code: str
    length_m: Decimal
    width_m: Decimal
    geom: dict[str, Any]
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime
