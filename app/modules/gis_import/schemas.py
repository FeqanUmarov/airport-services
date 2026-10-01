from typing import Any

from pydantic import BaseModel


class ShapefilePreviewResponse(BaseModel):
    file_name: str
    source_crs: str
    feature_count: int
    geometry_types: list[str]
    fields: list[str]
    bbox: list[float] | None
    feature_collection: dict[str, Any]
