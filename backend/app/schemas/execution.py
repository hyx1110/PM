from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel


class ExecutionCreate(ORMModel):
    task_id: int
    user_id: int | None = None
    actual_start: datetime
    actual_end: datetime | None = None
    actual_hours: Decimal | None = Field(default=None, ge=0)
    status: str = "running"
    description: str | None = None
    exception_reason: str | None = None

    @model_validator(mode="after")
    def validate_time(self):
        if self.actual_end and self.actual_end < self.actual_start:
            raise ValueError("actual_end must be on or after actual_start")
        return self


class ExecutionUpdate(ORMModel):
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    actual_hours: Decimal | None = Field(default=None, ge=0)
    status: str | None = None
    description: str | None = None
    exception_reason: str | None = None


class ExecutionResponse(ORMModel):
    id: int
    task_id: int
    task_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    user_id: int
    user_name: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime
    actual_end: datetime | None
    actual_hours: Decimal
    status: str
    description: str | None
    exception_reason: str | None
    created_at: datetime
    updated_at: datetime

