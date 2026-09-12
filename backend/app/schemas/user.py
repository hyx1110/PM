from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ORMModel
from app.utils.username import USERNAME_ERROR, is_valid_username, normalize_username


class UserCreate(ORMModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    department_id: int | None = None
    organization_id: int | None = None
    supervisor_id: int | None = None
    status: str = "active"
    role_ids: list[int] = []

    @field_validator("username", mode="before")
    @classmethod
    def normalize_new_username(cls, value):
        return normalize_username(value) if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def validate_new_username(cls, value: str) -> str:
        if not is_valid_username(value):
            raise ValueError(USERNAME_ERROR)
        return value

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class UserUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    department_id: int | None = None
    organization_id: int | None = None
    supervisor_id: int | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_ids: list[int] | None = None

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class UserResponse(ORMModel):
    id: int
    username: str
    name: str
    email: str | None
    phone: str | None
    department_id: int | None
    department_name: str | None = None
    organization_id: int | None
    organization_name: str | None = None
    supervisor_id: int | None
    supervisor_name: str | None = None
    status: str
    roles: list[str] = []
    role_ids: list[int] = []
    created_at: datetime
    updated_at: datetime


class AssignRolesRequest(ORMModel):
    role_ids: list[int]
