from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role_codes: list[str] = Field(default_factory=lambda: ["VIEWER"], min_length=1)

    @field_validator("username", "first_name", "last_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("role_codes")
    @classmethod
    def normalize_roles(cls, value: list[str]) -> list[str]:
        return sorted({role.strip().upper() for role in value})


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("username", "first_name", "last_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class UserStatusUpdate(BaseModel):
    status_id: int = Field(gt=0)


class UserRolesUpdate(BaseModel):
    role_codes: list[str] = Field(min_length=1)

    @field_validator("role_codes")
    @classmethod
    def normalize_roles(cls, value: list[str]) -> list[str]:
        return sorted({role.strip().upper() for role in value})


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    status_id: int
    status: str
    roles: list[str]
    created_date: datetime
    last_edited_date: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
