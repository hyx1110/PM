from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel


PROJECT_STATUSES = {"Draft", "Planned", "Running", "Suspended", "Completed", "Cancelled"}


class ProjectBase(ORMModel):
    name: str = Field(min_length=1, max_length=200)
    project_type: str = Field(default="General", max_length=50)
    manager_id: int
    department_id: int | None = None
    status: str = "Draft"
    planned_start: date
    planned_end: date
    actual_start: date | None = None
    actual_end: date | None = None
    priority: str = "medium"
    description: str | None = None
    remark: str | None = None

    @model_validator(mode="after")
    def validate_project(self):
        if self.status not in PROJECT_STATUSES:
            raise ValueError("invalid project status")
        if self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start")
        if self.actual_start and self.actual_end and self.actual_end < self.actual_start:
            raise ValueError("actual_end must be on or after actual_start")
        return self


class ProjectCreate(ProjectBase):
    code: str = Field(min_length=1, max_length=50)


class ProjectUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_type: str | None = None
    manager_id: int | None = None
    department_id: int | None = None
    status: str | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    priority: str | None = None
    description: str | None = None
    remark: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    code: str
    manager_name: str | None = None
    department_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectMemberCreate(ORMModel):
    user_id: int
    project_role: str = "member"
    allocation_percent: Decimal = Field(default=100, ge=0, le=100)
    joined_at: datetime


class ProjectMemberResponse(ORMModel):
    id: int
    project_id: int
    user_id: int
    user_name: str | None = None
    project_role: str
    allocation_percent: Decimal
    joined_at: datetime
    left_at: datetime | None
    created_at: datetime
    updated_at: datetime

