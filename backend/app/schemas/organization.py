from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import ORMModel


class DepartmentCreate(ORMModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    manager_id: int | None = None
    status: str = "active"


class DepartmentUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    manager_id: int | None = None
    status: str | None = None


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
    def validate_level(self):
        if self.level not in {"L1", "L2", "L3", "L4"}:
            raise ValueError("level must be L1, L2, L3 or L4")
        return self


class OrganizationUpdate(ORMModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    level: str | None = None
    manager_id: int | None = None
    status: str | None = None


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
    children: list["OrganizationNode"] = []
