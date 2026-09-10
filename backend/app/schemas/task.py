from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

TASK_TYPES = {"Project", "Routine", "Training", "Leave", "Other"}
TASK_STATUSES = {"not_started", "pending", "confirmed", "running", "completed", "delayed", "cancelled"}


class TaskBase(ORMModel):
    project_id: int
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    task_type: str = "Project"
    owner_id: int
    planned_start: datetime
    planned_end: datetime
    estimated_hours: Decimal = Field(default=0, ge=0)
    status: str = "not_started"
    priority: str = "medium"
    description: str | None = None
    remark: str | None = None

    @model_validator(mode="after")
    def validate_task(self):
        if self.task_type not in TASK_TYPES:
            raise ValueError("invalid task type")
        if self.status not in TASK_STATUSES:
            raise ValueError("invalid task status")
        if self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start")
        return self


class TaskCreate(TaskBase):
    pass


class TaskUpdate(ORMModel):
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: str | None = None
    owner_id: int | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    status: str | None = None
    priority: str | None = None
    description: str | None = None
    remark: str | None = None


class TaskResponse(TaskBase):
    id: int
    project_name: str | None = None
    owner_name: str | None = None
    effective_status: str
    created_at: datetime
    updated_at: datetime

