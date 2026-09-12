from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

SCHEDULE_STATUSES = {
    "draft",
    "pending",
    "confirmed",
    "rejected",
    "changed",
    "running",
    "completed",
    "cancelled",
    "withdrawn",
}


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
    source_booking_id: int | None = None
    version: int = 1
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


class ScheduleMove(ORMModel):
    start_time: datetime
    end_time: datetime
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class ScheduleBatchCreate(ORMModel):
    user_ids: list[int] = Field(min_length=1, max_length=100)
    project_id: int
    task_id: int
    start_time: datetime
    end_time: datetime
    planned_hours: Decimal | None = Field(default=None, ge=0)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_batch(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        if len(set(self.user_ids)) != len(self.user_ids):
            raise ValueError("user_ids must not contain duplicates")
        return self


class ScheduleCopyWeek(ORMModel):
    source_week_start: datetime
    target_week_start: datetime
    user_ids: list[int] = []
    include_statuses: list[str] = ["pending", "confirmed"]

    @model_validator(mode="after")
    def validate_weeks(self):
        if self.source_week_start == self.target_week_start:
            raise ValueError("source and target week must be different")
        invalid = set(self.include_statuses) - SCHEDULE_STATUSES
        if invalid:
            raise ValueError(f"invalid statuses: {', '.join(sorted(invalid))}")
        return self
