from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.report_repository import report_repository
from app.services.project_service import visible_project_ids
from app.services.task_service import effective_status


def process_report(db: Session, user: User, page: int, page_size: int, **filters):
    items, total = report_repository.process_report(
        db,
        page,
        page_size,
        visible_project_ids=visible_project_ids(db, user),
        **filters,
    )
    for item in items:
        item["effective_status"] = effective_status(item.pop("status"), item["planned_end"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def workload_report(db: Session, user: User, start_date: date, end_date: date, department_id: int | None, user_id: int | None):
    rows = report_repository.workload(
        db,
        start_date,
        end_date,
        department_id,
        user_id,
        visible_project_ids(db, user),
    )
    available = Decimal(str(settings.standard_work_hours))
    for item in rows:
        planned = Decimal(str(item["planned_hours"] or 0))
        rate = ((planned / available) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if available else Decimal("0")
        item.update(available_hours=available, load_rate=rate, overloaded=rate > 100)
    return rows


def dashboard_summary(db: Session, user: User) -> dict:
    scope = visible_project_ids(db, user)
    project_filters = [Project.is_deleted.is_(False)]
    task_filters = []
    schedule_filters = []
    if scope is not None:
        ids = scope or {-1}
        project_filters.append(Project.id.in_(ids))
        task_filters.append(Task.project_id.in_(ids))
        schedule_filters.append(ScheduleBooking.project_id.in_(ids))
    now = datetime.now()
    today = now.date()
    project_total = db.scalar(select(func.count(Project.id)).where(*project_filters)) or 0
    project_running = db.scalar(select(func.count(Project.id)).where(*project_filters, Project.status == "Running")) or 0
    delayed_tasks = db.scalar(
        select(func.count(Task.id)).where(
            *task_filters,
            Task.planned_end < now,
            Task.status.notin_({"completed", "cancelled"}),
        )
    ) or 0
    pending = db.scalar(select(func.count(ScheduleBooking.id)).where(*schedule_filters, ScheduleBooking.status.in_({"pending", "changed"}))) or 0
    today_count = db.scalar(
        select(func.count(ScheduleBooking.id)).where(
            *schedule_filters,
            func.date(ScheduleBooking.start_time) == today,
        )
    ) or 0
    return {
        "projects_total": project_total,
        "projects_running": project_running,
        "delayed_tasks": delayed_tasks,
        "pending_schedules": pending,
        "today_schedules": today_count,
    }
