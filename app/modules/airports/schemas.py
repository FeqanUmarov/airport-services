from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PointGeometry(BaseModel):
    type: Literal["Point"]
    coordinates: tuple[float, float]

    @field_validator("coordinates")
    @classmethod
    def valid_coordinates(cls, value: tuple[float, float]) -> tuple[float, float]:
        longitude, latitude = value
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("Point coordinates must be valid WGS84 longitude/latitude")
        return value


class BoundaryGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def non_empty_coordinates(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("Boundary coordinates cannot be empty")
        return value


class AirportCreate(BaseModel):
    icao_id: int = Field(gt=0)
    iata_code: str | None = Field(default=None, min_length=3, max_length=3)
    aze_name: str = Field(min_length=1, max_length=255)
    eng_name: str = Field(min_length=1, max_length=255)
    country_id: int = Field(gt=0)
    city_id: int = Field(gt=0)
    elevation_m: Decimal
    arp_geom: PointGeometry
    boundary_geom: BoundaryGeometry

    @field_validator("iata_code")
    @classmethod
    def normalize_iata(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("aze_name", "eng_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()


class AirportUpdate(BaseModel):
    icao_id: int | None = Field(default=None, gt=0)
    iata_code: str | None = Field(default=None, min_length=3, max_length=3)
    aze_name: str | None = Field(default=None, min_length=1, max_length=255)
    eng_name: str | None = Field(default=None, min_length=1, max_length=255)
    country_id: int | None = Field(default=None, gt=0)
    city_id: int | None = Field(default=None, gt=0)
    elevation_m: Decimal | None = None
    arp_geom: PointGeometry | None = None
    boundary_geom: BoundaryGeometry | None = None

    @field_validator("iata_code")
    @classmethod
    def normalize_iata(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("aze_name", "eng_name")
    @classmethod
    def strip_names(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "AirportUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class AirportStatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class AirportResponse(BaseModel):
    air_id: int
    icao_id: int
    icao_code: str
    iata_code: str | None
    aze_name: str
    eng_name: str
    country_id: int
    country_name: str
    city_id: int
    city_name: str
    elevation_m: Decimal
    arp_geom: dict[str, Any]
    boundary_geom: dict[str, Any]
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class AirportListResponse(BaseModel):
    items: list[AirportResponse]
    total: int
    page: int
    page_size: int
