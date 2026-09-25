from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

EXECUTION_STATUSES = {"running", "completed"}


class ExecutionCreate(ORMModel):
    task_id: int
    user_id: int | None = None
    actual_start: date
    actual_end: date | None = None
    actual_hours: Decimal | None = Field(default=None, gt=0)
    status: str = "running"
    description: str | None = None

    @model_validator(mode="after")
    def validate_time(self):
        if self.status not in EXECUTION_STATUSES:
            raise ValueError("invalid execution status")
        if self.actual_end and self.actual_end < self.actual_start:
            raise ValueError("actual_end must be on or after actual_start")
        if self.status == "completed" and self.actual_end is None:
            raise ValueError("completed execution must have actual_end")
        return self


class ExecutionUpdate(ORMModel):
    actual_start: date | None = None
    actual_end: date | None = None
    actual_hours: Decimal | None = Field(default=None, gt=0)
    status: str | None = None
    description: str | None = None


class ExecutionResponse(ORMModel):
    id: int
    task_id: int
    task_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    user_id: int
    user_name: str | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    estimated_hours: Decimal = Decimal("0")
    task_actual_hours: Decimal = Decimal("0")
    actual_start: date
    actual_end: date | None
    actual_hours: Decimal
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime
