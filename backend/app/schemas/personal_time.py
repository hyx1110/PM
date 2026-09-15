from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import ORMModel

PersonalTimeType = Literal[
    "training",
    "meeting",
    "leave",
    "out_of_office",
    "business_trip",
    "other",
]


class PersonalTimeCreate(ORMModel):
    time_type: PersonalTimeType
    start_time: datetime
    end_time: datetime
    remark: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class PersonalTimeResponse(ORMModel):
    id: int
    user_id: int
    user_name: str | None = None
    time_type: PersonalTimeType
    start_time: datetime
    end_time: datetime
    planned_hours: Decimal
    status: Literal["active", "withdrawn"]
    remark: str | None = None
    withdrawn_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
