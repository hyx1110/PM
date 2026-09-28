from datetime import datetime, time, timedelta

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.utils.time import BEIJING_TIMEZONE


class OvertimeCreate(ORMModel):
    task_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("start_time", "end_time")
    @classmethod
    def beijing_datetime(cls, value: datetime) -> datetime:
        return value.astimezone(BEIJING_TIMEZONE).replace(tzinfo=None) if value.tzinfo else value

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请填写加班原因")
        return value.strip()

    @model_validator(mode="after")
    def time_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("加班结束时间必须晚于开始时间")
        midnight_boundary = self.end_time == datetime.combine(self.start_time.date() + timedelta(days=1), time.min)
        if self.start_time.date() != self.end_time.date() and not midnight_boundary:
            raise ValueError("一条加班申请仅限同一天，跨日请拆分申请")
        if any(t.second or t.microsecond or t.minute not in {0, 30} for t in (self.start_time, self.end_time)):
            raise ValueError("加班时间请按半小时选择")
        return self


class OvertimeDecision(ORMModel):
    note: str | None = Field(default=None, max_length=2000)
