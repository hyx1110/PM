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
    planned_start: date
    planned_end: date
    actual_start: date | None
    actual_end: date | None
    estimated_hours: Decimal
    actual_hours: Decimal
    achievement_rate: Decimal | None
    achievement_quality: Decimal | None
    evaluation_id: int | None = None
    evaluated_at: datetime | None = None
    effective_status: str
    task_status: str
    can_evaluate: bool


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
    recent_14_day_planned_hours: float
    monthly_planned_hours: float
    weekly_utilization_rate: float
    recent_14_day_utilization_rate: float
    task_completion_rate: float
    schedule_trend: list[dict]
    planned_hours_scope: str
    planned_hours_description: str
