from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ORMModel


class DepartmentCreate(ORMModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    manager_id: int | None = None
    status: str = "active"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"active", "disabled"}:
            raise ValueError("status must be active or disabled")
        return value


class DepartmentUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    manager_id: int | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"active", "disabled"}:
            raise ValueError("status must be active or disabled")
        return value


class DepartmentResponse(ORMModel):
    id: int
    code: str
    name: str
    manager_id: int | None
    manager_name: str | None = None
    status: str
    data_source: str
    created_at: datetime
    updated_at: datetime


class OrganizationCreate(ORMModel):
    department_id: int
    parent_id: int | None = None
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    level: str
    manager_id: int | None = None
    status: str = "active"

    @model_validator(mode="after")
    def validate_values(self):
        if self.level not in {"L1", "L2", "L3", "L4"}:
            raise ValueError("level must be L1, L2, L3 or L4")
        if self.status not in {"active", "disabled"}:
            raise ValueError("status must be active or disabled")
        return self


class OrganizationUpdate(ORMModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    level: str | None = None
    manager_id: int | None = None
    status: str | None = None

    @model_validator(mode="after")
    def validate_values(self):
        if self.level is not None and self.level not in {"L1", "L2", "L3", "L4"}:
            raise ValueError("level must be L1, L2, L3 or L4")
        if self.status is not None and self.status not in {"active", "disabled"}:
            raise ValueError("status must be active or disabled")
        return self


class OrganizationUserNode(ORMModel):
    id: int
    employee_no: str
    name: str
    status: str


class OrganizationNode(ORMModel):
    id: int
    department_id: int
    parent_id: int | None
    code: str
    name: str
    level: str
    manager_id: int | None
    manager_name: str | None = None
    status: str
    data_source: str
    users: list[OrganizationUserNode] = Field(default_factory=list)
    children: list["OrganizationNode"] = Field(default_factory=list)
