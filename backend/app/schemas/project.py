from datetime import date, datetime
from decimal import Decimal
from pydantic import Field, model_validator

from app.schemas.common import ORMModel


PROJECT_STATUSES = {"Draft", "Planned", "Running", "Suspended", "Completed", "Cancelled"}
PROJECT_APPROVAL_STATUSES = {"draft", "pending", "approved", "rejected"}
RESOURCE_REQUEST_STATUSES = {"pending", "approved", "rejected"}


class ProjectBase(ORMModel):
    name: str = Field(min_length=1, max_length=200)
    manager_id: int
    department_id: int
    budget_hours: Decimal = Field(gt=0, decimal_places=2)
    planned_start: date
    planned_end: date
    description: str | None = None
    remark: str | None = None

    @model_validator(mode="after")
    def validate_project(self):
        if self.planned_end < self.planned_start:
            raise ValueError("planned_end must be on or after planned_start")
        return self


class ProjectCreate(ProjectBase):
    member_ids: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_initial_members(self):
        self.member_ids = list(dict.fromkeys(self.member_ids))
        if self.manager_id in self.member_ids:
            raise ValueError("member_ids must not contain the project manager")
        if not self.member_ids:
            raise ValueError("at least one project member is required")
        return self


class ProjectUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    manager_id: int | None = None
    department_id: int | None = None
    budget_hours: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    status: str | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    description: str | None = None
    remark: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    code: str
    manager_name: str | None = None
    manager_employee_no: str | None = None
    manager_organization_id: int | None = None
    manager_organization_name: str | None = None
    department_name: str | None = None
    department_manager_id: int | None = None
    status: str
    actual_start: date | None = None
    actual_end: date | None = None
    priority: str = "medium"
    approval_status: str
    created_by: int | None = None
    creator_name: str | None = None
    approver_id: int | None = None
    approval_required_name: str | None = None
    approved_by: int | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    approval_note: str | None = None
    booked_hours: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")
    can_manage: bool = False
    all_tasks_completed: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectMemberResponse(ORMModel):
    id: int
    project_id: int
    user_id: int
    user_name: str | None = None
    project_role: str
    joined_at: datetime
    left_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectDecision(ORMModel):
    note: str | None = Field(default=None, max_length=1000)


class ProjectResourceRequestCreate(ORMModel):
    requested_hours: Decimal = Field(default=0, ge=0, decimal_places=2)
    add_member_ids: list[int] = Field(default_factory=list)
    remove_member_ids: list[int] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_resources(self):
        self.add_member_ids = list(dict.fromkeys(self.add_member_ids))
        self.remove_member_ids = list(dict.fromkeys(self.remove_member_ids))
        if set(self.add_member_ids) & set(self.remove_member_ids):
            raise ValueError("the same member cannot be added and removed")
        if self.requested_hours <= 0 and not self.add_member_ids and not self.remove_member_ids:
            raise ValueError("at least one resource change is required")
        return self


class ProjectResourceRequestResponse(ORMModel):
    id: int
    project_id: int
    requested_hours: Decimal
    add_member_ids: list[int] = Field(default_factory=list)
    remove_member_ids: list[int] = Field(default_factory=list)
    reason: str
    status: str
    requested_by: int
    requester_name: str | None = None
    project_code: str | None = None
    project_name: str | None = None
    reviewed_by: int | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime
