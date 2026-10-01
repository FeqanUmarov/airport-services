from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OlsRevisionRestoreRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class OlsRevisionResponse(BaseModel):
    revision_id: int
    ols_surface_id: int
    revision_no: int
    standard_ols_id: int
    generation_method_id: int
    air_id: int
    run_id: int | None
    run_dir_id: int | None
    aze_name: str | None
    eng_name: str | None
    geometry: dict[str, Any]
    status_id: int
    change_type: str
    change_note: str | None
    created_by: int | None
    created_date: datetime
