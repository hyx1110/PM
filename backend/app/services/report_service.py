from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project
from app.models.risk import RiskRecord
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.report_repository import report_repository
from app.services.task_service import effective_status
from app.services.visibility_service import visible_schedule_user_ids
from app.services.work_calendar_service import is_workday
from app.utils.time import beijing_now


def process_report(db: Session, user: User, page: int, page_size: int, **filters):
    items, total = report_repository.process_report(
        db,
        page,
        page_size,
        visible_project_ids=None,
        **filters,
    )
    for item in items:
        item["task_status"] = item["status"]
        item["effective_status"] = effective_status(item.pop("status"), item["planned_end"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def workload_report(db: Session, user: User, start_date: date, end_date: date, department_id: int | None, user_id: int | None):
    rows = report_repository.workload(
        db,
        start_date,
        end_date,
        department_id,
        user_id,
        visible_project_ids=None,
        visible_user_ids=visible_schedule_user_ids(db, user),
    )
    for item in rows:
        work_date = item["date"]
        if not isinstance(work_date, date):
            work_date = date.fromisoformat(str(work_date))
        available = (
            Decimal(str(settings.standard_work_hours))
            if is_workday(db, work_date)
            else Decimal("0")
        )
        planned = Decimal(str(item["planned_hours"] or 0))
        rate = ((planned / available) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if available else Decimal("0")
        item.update(
            available_hours=available,
            load_rate=rate,
            overloaded=planned > available,
        )
    return rows


def dashboard_summary(db: Session, user: User) -> dict:
    schedule_user_ids = visible_schedule_user_ids(db, user)
    project_filters = [Project.is_deleted.is_(False)]
    active_project_ids = select(Project.id).where(Project.is_deleted.is_(False))
    task_filters = [
        Task.is_deleted.is_(False),
        Task.project_id.in_(active_project_ids),
    ]
    schedule_filters = [ScheduleBooking.project_id.in_(active_project_ids)]
    if schedule_user_ids is not None:
        schedule_filters.append(
            ScheduleBooking.user_id.in_(schedule_user_ids or {-1})
        )
    now = beijing_now()
    today = now.date()
    project_total = db.scalar(select(func.count(Project.id)).where(*project_filters)) or 0
    project_running = db.scalar(select(func.count(Project.id)).where(*project_filters, Project.status == "Running")) or 0
    project_completed = db.scalar(select(func.count(Project.id)).where(*project_filters, Project.status == "Completed")) or 0
    delayed_projects = db.scalar(
        select(func.count(Project.id)).where(
            *project_filters,
            Project.planned_end < today,
            Project.status.notin_({"Completed", "Cancelled"}),
        )
    ) or 0
    delayed_tasks = db.scalar(
        select(func.count(Task.id)).where(
            *task_filters,
            Task.planned_end < now,
            Task.status.notin_({"completed", "cancelled"}),
        )
    ) or 0
    pending = db.scalar(
        select(func.count(ScheduleBooking.id)).where(
            ScheduleBooking.user_id == user.id,
            ScheduleBooking.status.in_({"pending", "changed"}),
        )
    ) or 0
    pending_project_approvals = db.scalar(
        select(func.count(Project.id)).where(
            Project.approver_id == user.id,
            Project.approval_status == "pending",
            Project.is_deleted.is_(False),
        )
    ) or 0
    start_of_today = datetime.combine(today, datetime.min.time())
    start_of_tomorrow = start_of_today + timedelta(days=1)
    my_today_tasks = db.scalar(
        select(func.count(Task.id)).where(
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user.id)),
            Task.is_deleted.is_(False),
            Task.status.notin_({"completed", "cancelled"}),
            Task.planned_start < start_of_tomorrow,
            Task.planned_end >= start_of_today,
        )
    ) or 0
    my_upcoming_tasks = db.scalar(
        select(func.count(Task.id)).where(
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user.id)),
            Task.is_deleted.is_(False),
            Task.status.notin_({"completed", "cancelled"}),
            Task.planned_end >= start_of_tomorrow,
            Task.planned_end < start_of_tomorrow + timedelta(days=7),
        )
    ) or 0
    today_count = db.scalar(
        select(func.count(ScheduleBooking.id)).where(
            *schedule_filters,
            ScheduleBooking.status.in_(
                {"pending", "confirmed", "changed", "running", "completed"}
            ),
            func.date(ScheduleBooking.start_time) == today,
        )
    ) or 0
    risk_filters = [RiskRecord.status.in_({"open", "handling"})]
    if schedule_user_ids is not None:
        risk_filters.append(RiskRecord.user_id.in_(schedule_user_ids or {-1}))
    open_risks = db.scalar(select(func.count(RiskRecord.id)).where(*risk_filters)) or 0
    critical_risks = db.scalar(
        select(func.count(RiskRecord.id)).where(*risk_filters, RiskRecord.risk_level == "critical")
    ) or 0
    today_risks = db.scalar(
        select(func.count(RiskRecord.id)).where(*risk_filters, func.date(RiskRecord.detected_at) == today)
    ) or 0
    week_start = today - timedelta(days=today.weekday())
    week_hours = db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(
            *schedule_filters,
            ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
            ScheduleBooking.start_time >= datetime.combine(week_start, datetime.min.time()),
            ScheduleBooking.start_time < datetime.combine(week_start + timedelta(days=7), datetime.min.time()),
        )
    ) or 0
    month_start = today.replace(day=1)
    next_month_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_hours = db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(
            *schedule_filters,
            ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
            ScheduleBooking.start_time >= datetime.combine(month_start, datetime.min.time()),
            ScheduleBooking.start_time < datetime.combine(next_month_start, datetime.min.time()),
        )
    ) or 0
    active_user_filters = [User.status == "active", User.is_deleted.is_(False)]
    if schedule_user_ids is not None:
        active_user_filters.append(User.id.in_(schedule_user_ids or {-1}))
    active_users = db.scalar(select(func.count(User.id)).where(*active_user_filters)) or 0
    weekly_workdays = sum(
        is_workday(db, week_start + timedelta(days=index)) for index in range(7)
    )
    weekly_capacity = active_users * weekly_workdays * settings.standard_work_hours
    total_tasks = db.scalar(select(func.count(Task.id)).where(*task_filters)) or 0
    completed_tasks = db.scalar(
        select(func.count(Task.id)).where(*task_filters, Task.status == "completed")
    ) or 0
    trend_start = today - timedelta(days=13)
    trend_rows = db.execute(
        select(
            func.date(ScheduleBooking.start_time).label("day"),
            func.sum(ScheduleBooking.planned_hours).label("hours"),
        )
        .where(
            *schedule_filters,
            ScheduleBooking.start_time >= datetime.combine(trend_start, datetime.min.time()),
            ScheduleBooking.start_time < datetime.combine(today + timedelta(days=1), datetime.min.time()),
            ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
        )
        .group_by(func.date(ScheduleBooking.start_time))
    ).all()
    trend_map = {str(day): float(hours or 0) for day, hours in trend_rows}
    trend = [
        {
            "date": (trend_start + timedelta(days=index)).isoformat(),
            "planned_hours": trend_map.get((trend_start + timedelta(days=index)).isoformat(), 0),
        }
        for index in range(14)
    ]
    return {
        "projects_total": project_total,
        "projects_running": project_running,
        "projects_completed": project_completed,
        "projects_delayed": delayed_projects,
        "delayed_tasks": delayed_tasks,
        "pending_schedules": pending,
        "pending_project_approvals": pending_project_approvals,
        "my_today_tasks": my_today_tasks,
        "my_upcoming_tasks": my_upcoming_tasks,
        "today_schedules": today_count,
        "open_risks": open_risks,
        "critical_risks": critical_risks,
        "today_risks": today_risks,
        "weekly_planned_hours": float(week_hours),
        "monthly_planned_hours": float(month_hours),
        "weekly_utilization_rate": round(float(week_hours) / weekly_capacity * 100, 2) if weekly_capacity else 0,
        "task_completion_rate": round(completed_tasks / total_tasks * 100, 2) if total_tasks else 0,
        "schedule_trend": trend,
    }


def _validate_range(start_date: date, end_date: date) -> None:
    from app.core.exceptions import bad_request

    if end_date < start_date:
        raise bad_request("end_date must be on or after start_date")
    if (end_date - start_date).days > 366:
        raise bad_request("report range cannot exceed 366 days")


def workload_summary(db: Session, user: User, start_date: date, end_date: date, granularity: str) -> dict:
    _validate_range(start_date, end_date)
    if granularity not in {"day", "week", "month"}:
        from app.core.exceptions import bad_request
        raise bad_request("granularity must be day, week or month")
    visible_user_ids = visible_schedule_user_ids(db, user)
    filters = [
        ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
        ScheduleBooking.project_id.in_(
            select(Project.id).where(Project.is_deleted.is_(False))
        ),
        ScheduleBooking.start_time >= datetime.combine(start_date, datetime.min.time()),
        ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
    ]
    if visible_user_ids is not None:
        filters.append(ScheduleBooking.user_id.in_(visible_user_ids or {-1}))
    rows = db.execute(
        select(ScheduleBooking, User.name, Project.name)
        .join(User, User.id == ScheduleBooking.user_id)
        .join(Project, Project.id == ScheduleBooking.project_id)
        .where(*filters)
    ).all()
    periods: dict[str, dict] = {}
    user_totals: dict[int, dict] = {}
    project_totals: dict[int, dict] = {}
    for item, user_name, project_name in rows:
        work_date = item.start_time.date()
        if granularity == "day":
            period = work_date.isoformat()
        elif granularity == "week":
            monday = work_date - timedelta(days=work_date.weekday())
            period = monday.isoformat()
        else:
            period = work_date.strftime("%Y-%m")
        hours = float(item.planned_hours or 0)
        bucket = periods.setdefault(period, {"period": period, "planned_hours": 0.0})
        bucket["planned_hours"] += hours
        user_bucket = user_totals.setdefault(item.user_id, {"user_id": item.user_id, "user_name": user_name, "planned_hours": 0.0})
        user_bucket["planned_hours"] += hours
        project_bucket = project_totals.setdefault(item.project_id, {"project_id": item.project_id, "project_name": project_name, "planned_hours": 0.0})
        project_bucket["planned_hours"] += hours
    eligible_user_filters = [User.status == "active", User.is_deleted.is_(False)]
    if visible_user_ids is not None:
        eligible_user_filters.append(User.id.in_(visible_user_ids or {-1}))
    for eligible_user in db.scalars(select(User).where(*eligible_user_filters)).all():
        user_totals.setdefault(
            eligible_user.id,
            {"user_id": eligible_user.id, "user_name": eligible_user.name, "planned_hours": 0.0},
        )
    workdays = sum(
        is_workday(db, start_date + timedelta(days=index))
        for index in range((end_date - start_date).days + 1)
    )
    available = workdays * settings.standard_work_hours
    for item in user_totals.values():
        item["available_hours"] = available
        item["load_rate"] = round(item["planned_hours"] / available * 100, 2) if available else 0
        item["load_status"] = "overloaded" if item["load_rate"] > 100 else ("idle" if item["load_rate"] < 50 else "normal")
        item["planned_hours"] = round(item["planned_hours"], 2)
    total_hours = sum(item["planned_hours"] for item in project_totals.values())
    for item in project_totals.values():
        item["share"] = round(item["planned_hours"] / total_hours * 100, 2) if total_hours else 0
        item["planned_hours"] = round(item["planned_hours"], 2)
    for item in periods.values():
        item["planned_hours"] = round(item["planned_hours"], 2)
    return {
        "range": {"start_date": start_date, "end_date": end_date, "granularity": granularity},
        "periods": sorted(periods.values(), key=lambda item: item["period"]),
        "users": sorted(user_totals.values(), key=lambda item: item["load_rate"], reverse=True),
        "projects": sorted(project_totals.values(), key=lambda item: item["planned_hours"], reverse=True),
    }
