from datetime import datetime

from pydantic import AliasChoices, EmailStr, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.employee_profile import (
    EmployeeProfileCreate,
    EmployeeProfileResponse,
    EmployeeProfileUpdate,
)
from app.utils.username import EMPLOYEE_NO_ERROR, is_valid_username, normalize_username


class UserCreate(ORMModel):
    employee_no: str = Field(
        min_length=2,
        max_length=50,
        validation_alias=AliasChoices("employee_no", "username"),
    )
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    department_id: int | None = None
    organization_id: int | None = None
    supervisor_id: int | None = None
    status: str = "active"
    role_ids: list[int] = []
    employee_profile: EmployeeProfileCreate = Field(
        default_factory=EmployeeProfileCreate
    )

    @field_validator("employee_no", mode="before")
    @classmethod
    def normalize_employee_no(cls, value):
        return normalize_username(value) if isinstance(value, str) else value

    @field_validator("employee_no")
    @classmethod
    def validate_employee_no(cls, value: str) -> str:
        if not is_valid_username(value):
            raise ValueError(EMPLOYEE_NO_ERROR)
        return value

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError("初始密码与确认密码不一致")
        return self


class UserUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=60)
    department_id: int | None = None
    organization_id: int | None = None
    supervisor_id: int | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    confirm_password: str | None = Field(default=None, min_length=8, max_length=128)
    role_ids: list[int] | None = None
    employee_profile: EmployeeProfileUpdate | None = None

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password is None and self.confirm_password is not None:
            raise ValueError("请先填写新密码")
        if self.password is not None and self.password != self.confirm_password:
            raise ValueError("新密码与确认密码不一致")
        return self


class UserResponse(ORMModel):
    id: int
    employee_no: str
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
    manual_role_ids: list[int] = []
    hr_role_ids: list[int] = []
    manual_roles: list[str] = []
    hr_roles: list[str] = []
    employee_profile: EmployeeProfileResponse | None = None
    created_at: datetime
    updated_at: datetime


class AssignRolesRequest(ORMModel):
    role_ids: list[int]
