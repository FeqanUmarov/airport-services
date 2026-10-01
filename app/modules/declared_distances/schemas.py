from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class DeclaredDistanceUpsert(BaseModel):
    tora_m: Decimal = Field(gt=0)
    toda_m: Decimal = Field(gt=0)
    asda_m: Decimal = Field(gt=0)
    lda_m: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_operational_relationships(self) -> "DeclaredDistanceUpsert":
        if self.toda_m < self.tora_m:
            raise ValueError("TODA must be greater than or equal to TORA")
        if self.asda_m < self.tora_m:
            raise ValueError("ASDA must be greater than or equal to TORA")
        return self


class DeclaredDistanceStatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class DeclaredDistanceResponse(BaseModel):
    declared_distance_id: int
    run_dir_id: int
    run_id: int
    designator: str
    tora_m: Decimal
    toda_m: Decimal
    asda_m: Decimal
    lda_m: Decimal
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime
