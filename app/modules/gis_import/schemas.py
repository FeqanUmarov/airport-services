from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


class ShapefilePreviewResponse(BaseModel):
    file_name: str
    source_crs: str
    feature_count: int
    geometry_types: list[str]
    fields: list[str]
    bbox: list[float] | None
    feature_collection: dict[str, Any]


class ShapefileImportMetadata(BaseModel):
    target: Literal["RUNWAY", "STRIP", "RUNWAY_AREA", "OLS"]
    air_id: int
    run_id: int | None = None
    run_dir_id: int | None = None
    standard_ols_id: int | None = None
    area_type_id: int | None = None
    aze_name: str | None = None
    eng_name: str | None = None
    designator_1: str | None = None
    designator_2: str | None = None
    length_m: Decimal | None = None
    width_m: Decimal | None = None
    default_elevation_m: Decimal | None = None


class ShapefileImportResponse(BaseModel):
    target: str
    imported_count: int
    object_ids: list[int]
    source_crs: str
    geometry_types: list[str]
