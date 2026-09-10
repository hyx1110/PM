from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

SCHEDULE_STATUSES = {"draft", "pending", "confirmed", "rejected", "changed", "running", "completed", "cancelled"}


class ScheduleCreate(ORMModel):
    user_id: int
    project_id: int
    task_id: int
    start_time: datetime
    end_time: datetime
    planned_hours: Decimal | None = Field(default=None, ge=0)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class ScheduleUpdate(ORMModel):
    user_id: int | None = None
    project_id: int | None = None
    task_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    planned_hours: Decimal | None = Field(default=None, ge=0)
    remark: str | None = None


class ScheduleResponse(ORMModel):
    id: int
    user_id: int
    user_name: str | None = None
    department_id: int | None = None
    project_id: int
    project_name: str | None = None
    task_id: int
    task_name: str | None = None
    task_type: str | None = None
    start_time: datetime
    end_time: datetime
    planned_hours: Decimal
    status: str
    remark: str | None
    rejection_reason: str | None
    created_by: int
    has_conflict: bool = False
    created_at: datetime
    updated_at: datetime


class ScheduleDecision(ORMModel):
    reason: str | None = Field(default=None, max_length=1000)


class ScheduleConflict(ORMModel):
    schedule_id: int
    project_id: int
    project_name: str
    task_id: int
    task_name: str
    user_id: int
    user_name: str
    start_time: datetime
    end_time: datetime

