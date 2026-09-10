from datetime import date, datetime
from decimal import Decimal

from app.schemas.common import ORMModel


class ProcessReportItem(ORMModel):
    project_id: int
    project_name: str
    level1_task: str | None
    level2_task: str | None
    task_id: int
    owner_id: int
    owner_name: str
    planned_start: datetime
    planned_end: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    estimated_hours: Decimal
    actual_hours: Decimal
    achievement_rate: Decimal | None
    achievement_quality: Decimal | None
    effective_status: str


class WorkloadItem(ORMModel):
    user_id: int
    user_name: str
    date: date
    planned_hours: Decimal
    available_hours: Decimal
    load_rate: Decimal
    overloaded: bool


class DashboardSummary(ORMModel):
    projects_total: int
    projects_running: int
    delayed_tasks: int
    pending_schedules: int
    today_schedules: int

