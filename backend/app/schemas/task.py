from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

TASK_TYPES = {"Project", "Routine", "Training", "Leave", "Other"}
TASK_STATUSES = {"not_started", "running", "completed", "suspended", "cancelled"}
TASK_FILTER_STATUSES = TASK_STATUSES | {"delayed"}


class TaskBase(ORMModel):
    project_id: int
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    task_type: str = "Project"
    planned_start: date
    planned_end: date
    estimated_hours: Decimal = Field(default=0, ge=0)
    description: str | None = None
    remark: str | None = None

    @model_validator(mode="after")
    def validate_task(self):
        if self.task_type not in TASK_TYPES:
            raise ValueError("invalid task type")
        if self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start")
        return self


class TaskCreate(TaskBase):
    owner_ids: list[int] = Field(min_length=1)


class TaskUpdate(ORMModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: str | None = None
    owner_ids: list[int] | None = Field(default=None, min_length=1)
    planned_start: date | None = None
    planned_end: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    status: str | None = None
    description: str | None = None
    remark: str | None = None


class TaskResponse(TaskBase):
    id: int
    owner_id: int
    owner_ids: list[int] = Field(default_factory=list)
    owner_names: list[str] = Field(default_factory=list)
    status: str
    priority: str = "medium"
    project_name: str | None = None
    owner_name: str | None = None
    project_manager_name: str | None = None
    project_manager_id: int | None = None
    can_manage: bool = False
    can_edit: bool = False
    can_delete: bool = False
    booked_hours: Decimal = Decimal("0")
    effective_status: str
    created_at: datetime
    updated_at: datetime
