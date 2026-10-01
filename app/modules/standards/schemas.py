from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class StandardCreate(BaseModel):
    standard_type_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=50)
    aze_name: str = Field(min_length=1, max_length=255)
    eng_name: str = Field(min_length=1, max_length=255)
    edition: str | None = Field(default=None, max_length=50)
    amendment: str | None = Field(default=None, max_length=50)
    effective_date: date
    description: str | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("aze_name", "eng_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("edition", "amendment", "description")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class StandardUpdate(BaseModel):
    standard_type_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    aze_name: str | None = Field(default=None, min_length=1, max_length=255)
    eng_name: str | None = Field(default=None, min_length=1, max_length=255)
    edition: str | None = Field(default=None, max_length=50)
    amendment: str | None = Field(default=None, max_length=50)
    effective_date: date | None = None
    description: str | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @model_validator(mode="after")
    def has_value(self) -> "StandardUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class StandardStatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class StandardResponse(BaseModel):
    standard_id: int
    standard_type_id: int
    standard_type_code: str
    standard_type_name: str
    code: str
    aze_name: str
    eng_name: str
    edition: str | None
    amendment: str | None
    effective_date: date
    description: str | None
    status_id: int
    status: str
    created_date: datetime
    last_edited_date: datetime


class StandardListResponse(BaseModel):
    items: list[StandardResponse]
    total: int
    page: int
    page_size: int


class StandardSurfaceCreate(BaseModel):
    surface_type_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=500)


class StandardSurfaceUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=500)
    status_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def has_value(self) -> "StandardSurfaceUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class StandardParameterUpsert(BaseModel):
    parameter_id: int = Field(gt=0)
    section_no: int = Field(default=0, ge=0, le=32767)
    numeric_value: Decimal | None = None
    boolean_value: bool | None = None
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exactly_one_value(self) -> "StandardParameterUpsert":
        if (self.numeric_value is None) == (self.boolean_value is None):
            raise ValueError("Exactly one numeric or boolean value must be supplied")
        return self


class StandardParameterResponse(BaseModel):
    param_value_id: int
    parameter_id: int
    parameter_code: str
    parameter_name: str
    section_no: int
    numeric_value: Decimal | None
    boolean_value: bool | None
    unit_id: int
    unit_code: str
    unit_symbol: str | None
    description: str | None
    status_id: int
    status: str


class StandardSurfaceResponse(BaseModel):
    standard_ols_id: int
    standard_id: int
    surface_type_id: int
    surface_type_code: str
    surface_type_name: str
    description: str | None
    status_id: int
    status: str
    parameters: list[StandardParameterResponse]


class StandardSurfaceListResponse(BaseModel):
    items: list[StandardSurfaceResponse]
    total: int
