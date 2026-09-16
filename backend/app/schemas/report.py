from datetime import date, datetime
from decimal import Decimal

from app.schemas.common import ORMModel


class ProcessReportItem(ORMModel):
    project_id: int
    project_name: str
    project_status: str
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
    task_status: str


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
    projects_completed: int
    projects_delayed: int
    delayed_tasks: int
    pending_schedules: int
    pending_project_approvals: int
    my_today_tasks: int
    my_upcoming_tasks: int
    today_schedules: int
    open_risks: int
    critical_risks: int
    today_risks: int
    weekly_planned_hours: float
    monthly_planned_hours: float
    weekly_utilization_rate: float
    task_completion_rate: float
    schedule_trend: list[dict]
