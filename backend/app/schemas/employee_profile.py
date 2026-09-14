from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ORMModel

HRManagementLevel = Literal[
    "employee",
    "department_manager",
    "management_manager",
]


class EmployeeProfileCreate(ORMModel):
    position_id: str | None = Field(default=None, max_length=20)
    employee_type: str | None = Field(default=None, max_length=1)
    local_f_name: str | None = Field(default=None, max_length=60)
    english_f_name: str | None = Field(default=None, max_length=60)
    local_g_name: str | None = Field(default=None, max_length=60)
    english_g_name: str | None = Field(default=None, max_length=60)
    preferred_name: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=1)
    job_id: str | None = Field(default=None, max_length=60)
    job_title: str | None = Field(default=None, max_length=60)
    eng_job_title: str | None = Field(default=None, max_length=60)
    chi_job_title: str | None = Field(default=None, max_length=60)
    degree: str | None = Field(default=None, max_length=60)
    staff_category: str | None = Field(default=None, max_length=1)
    site: str | None = Field(default=None, max_length=20)
    cost_center_code: str | None = Field(default=None, max_length=20)
    personnel_area: str | None = Field(default=None, max_length=60)
    personnel_sub_area: str | None = Field(default=None, max_length=60)
    hr_management_level: HRManagementLevel = "employee"

    @field_validator("*", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class EmployeeProfileUpdate(EmployeeProfileCreate):
    hr_management_level: HRManagementLevel | None = None


class EmployeeProfileResponse(EmployeeProfileCreate):
    id: int
    user_id: int
    hr_management_level: HRManagementLevel
    data_source: Literal["local", "hrdb"]
    synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
