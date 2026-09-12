from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ORMModel


class WorkCalendarDayUpsert(ORMModel):
    day_type: Literal["holiday", "workday"]
    name: str = Field(min_length=1, max_length=100)
    source: str | None = Field(default=None, max_length=255)


class WorkCalendarDayResponse(WorkCalendarDayUpsert):
    id: int
    work_date: date
    created_at: datetime
    updated_at: datetime
