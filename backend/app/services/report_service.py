from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_role_codes
from app.models.project import Project, ProjectMember
from app.models.evaluation import TaskEvaluation
from app.models.execution import ExecutionRecord
from app.models.risk import RiskRecord
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
    has_team_scope = bool(
        get_role_codes(db, user.id)
        & {
            "project_manager",
            "department_manager",
            "functional_manager",
            "super_admin",
        }
    )
    project_filters = [Project.is_deleted.is_(False)]
    task_filters = [Task.is_deleted.is_(False)]
    schedule_filters = []
    if scope is not None:
        ids = scope or {-1}
        project_filters.append(Project.id.in_(ids))
        task_filters.append(Task.project_id.in_(ids))
        schedule_filters.append(ScheduleBooking.project_id.in_(ids))
    if not has_team_scope:
        task_filters.append(Task.owner_id == user.id)
        schedule_filters.append(ScheduleBooking.user_id == user.id)
    now = datetime.now()
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
            Task.owner_id == user.id,
            Task.is_deleted.is_(False),
            Task.status.notin_({"completed", "cancelled"}),
            Task.planned_start < start_of_tomorrow,
            Task.planned_end >= start_of_today,
        )
    ) or 0
    my_upcoming_tasks = db.scalar(
        select(func.count(Task.id)).where(
            Task.owner_id == user.id,
            Task.is_deleted.is_(False),
            Task.status.notin_({"completed", "cancelled"}),
            Task.planned_end >= start_of_tomorrow,
            Task.planned_end < start_of_tomorrow + timedelta(days=7),
        )
    ) or 0
    today_count = db.scalar(
        select(func.count(ScheduleBooking.id)).where(
            *schedule_filters,
            func.date(ScheduleBooking.start_time) == today,
        )
    ) or 0
    risk_filters = [RiskRecord.status.in_({"open", "handling"})]
    if not has_team_scope:
        active_user_filters.append(User.id == user.id)
    elif scope is not None:
        risk_filters.append(
            (RiskRecord.project_id.in_(scope or {-1}))
            | (RiskRecord.project_id.is_(None) & (RiskRecord.user_id == user.id))
        )
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
    if scope is not None:
        member_ids = select(ProjectMember.user_id).where(
            ProjectMember.project_id.in_(scope or {-1}), ProjectMember.left_at.is_(None)
        )
        manager_ids = select(Project.manager_id).where(Project.id.in_(scope or {-1}))
        active_user_filters.append(
            (User.id.in_(member_ids)) | (User.id.in_(manager_ids)) | (User.id == user.id)
        )
    active_users = db.scalar(select(func.count(User.id)).where(*active_user_filters)) or 0
    weekly_capacity = active_users * 5 * settings.standard_work_hours
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


def analytics_report(db: Session, user: User, start_date: date, end_date: date) -> dict:
    _validate_range(start_date, end_date)
    scope = visible_project_ids(db, user)
    project_filters = [Project.is_deleted.is_(False)]
    task_filters = [Task.is_deleted.is_(False), Task.planned_end >= datetime.combine(start_date, datetime.min.time()), Task.planned_start < datetime.combine(end_date + timedelta(days=1), datetime.min.time())]
    schedule_filters = [ScheduleBooking.start_time >= datetime.combine(start_date, datetime.min.time()), ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()), ScheduleBooking.status.in_({"confirmed", "running", "completed"})]
    execution_filters = [ExecutionRecord.actual_start >= datetime.combine(start_date, datetime.min.time()), ExecutionRecord.actual_start < datetime.combine(end_date + timedelta(days=1), datetime.min.time())]
    if scope is not None:
        ids = scope or {-1}
        project_filters.append(Project.id.in_(ids))
        task_filters.append(Task.project_id.in_(ids))
        schedule_filters.append(ScheduleBooking.project_id.in_(ids))
        execution_filters.append(Task.project_id.in_(ids))

    projects = db.scalars(select(Project).where(*project_filters)).all()
    tasks = db.scalars(select(Task).where(*task_filters)).all()
    schedules = db.scalars(select(ScheduleBooking).where(*schedule_filters)).all()
    execution_rows = db.execute(
        select(ExecutionRecord, Task.project_id, Task.owner_id)
        .join(Task, Task.id == ExecutionRecord.task_id)
        .where(*execution_filters)
    ).all()
    evaluations = {
        task_id: (float(rate), float(quality))
        for task_id, rate, quality in db.execute(
            select(TaskEvaluation.task_id, TaskEvaluation.achievement_rate, TaskEvaluation.achievement_quality)
            .join(Task, Task.id == TaskEvaluation.task_id)
            .where(*task_filters)
        ).all()
    }
    project_names = {item.id: item.name for item in projects}
    user_names = dict(db.execute(select(User.id, User.name)).all())
    plan_by_day: dict[str, float] = defaultdict(float)
    actual_by_day: dict[str, float] = defaultdict(float)
    project_plan: dict[int, float] = defaultdict(float)
    project_actual: dict[int, float] = defaultdict(float)
    user_actual: dict[int, float] = defaultdict(float)
    project_user_actual: dict[tuple[int, int], float] = defaultdict(float)
    for item in schedules:
        hours = float(item.planned_hours or 0)
        plan_by_day[item.start_time.date().isoformat()] += hours
        project_plan[item.project_id] += hours
    for item, project_id, owner_id in execution_rows:
        hours = float(item.actual_hours or 0)
        actual_by_day[item.actual_start.date().isoformat()] += hours
        project_actual[project_id] += hours
        user_actual[item.user_id] += hours
        project_user_actual[(project_id, item.user_id)] += hours
    task_by_project: dict[int, list[Task]] = defaultdict(list)
    task_by_user: dict[int, list[Task]] = defaultdict(list)
    for item in tasks:
        task_by_project[item.project_id].append(item)
        task_by_user[item.owner_id].append(item)
    trend = []
    current = start_date
    while current <= end_date:
        key = current.isoformat()
        trend.append({"date": key, "planned_hours": round(plan_by_day[key], 2), "actual_hours": round(actual_by_day[key], 2)})
        current += timedelta(days=1)
    project_metrics = []
    for project in projects:
        related_tasks = task_by_project[project.id]
        completed = sum(item.status == "completed" for item in related_tasks)
        project_metrics.append({
            "project_id": project.id,
            "project_name": project.name,
            "planned_hours": round(project_plan[project.id], 2),
            "actual_hours": round(project_actual[project.id], 2),
            "task_completion_rate": round(completed / len(related_tasks) * 100, 2) if related_tasks else 0,
            "delayed": project.planned_end < end_date and project.status not in {"Completed", "Cancelled"},
        })
    member_metrics = []
    for user_id in sorted(set(task_by_user) | set(user_actual)):
        related_tasks = task_by_user[user_id]
        completed = [item for item in related_tasks if item.status == "completed"]
        rates = [evaluations[item.id][0] for item in related_tasks if item.id in evaluations]
        member_metrics.append({
            "user_id": user_id,
            "user_name": user_names.get(user_id, str(user_id)),
            "task_count": len(related_tasks),
            "completed_tasks": len(completed),
            "task_achievement_rate": round(sum(rates) / len(rates), 2) if rates else 0,
            "actual_hours": round(user_actual[user_id], 2),
        })
    workforce_share = []
    for (project_id, user_id), hours in sorted(project_user_actual.items(), key=lambda item: item[1], reverse=True):
        total = project_actual[project_id]
        workforce_share.append({
            "project_id": project_id,
            "project_name": project_names.get(project_id, str(project_id)),
            "user_id": user_id,
            "user_name": user_names.get(user_id, str(user_id)),
            "actual_hours": round(hours, 2),
            "share": round(hours / total * 100, 2) if total else 0,
        })
    total_tasks = len(tasks)
    total_plan = sum(plan_by_day.values())
    total_actual = sum(actual_by_day.values())
    return {
        "range": {"start_date": start_date, "end_date": end_date},
        "overview": {
            "project_count": len(projects),
            "task_count": total_tasks,
            "task_completion_rate": round(sum(item.status == "completed" for item in tasks) / total_tasks * 100, 2) if total_tasks else 0,
            "planned_hours": round(total_plan, 2),
            "actual_hours": round(total_actual, 2),
            "plan_actual_rate": round(total_actual / total_plan * 100, 2) if total_plan else 0,
            "project_delay_rate": round(sum(item["delayed"] for item in project_metrics) / len(project_metrics) * 100, 2) if project_metrics else 0,
        },
        "trend": trend,
        "projects": project_metrics,
        "members": member_metrics,
        "workforce_share": workforce_share,
    }


def workload_summary(db: Session, user: User, start_date: date, end_date: date, granularity: str) -> dict:
    _validate_range(start_date, end_date)
    if granularity not in {"day", "week", "month"}:
        from app.core.exceptions import bad_request
        raise bad_request("granularity must be day, week or month")
    scope = visible_project_ids(db, user)
    filters = [
        ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
        ScheduleBooking.start_time >= datetime.combine(start_date, datetime.min.time()),
        ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
    ]
    if scope is not None:
        filters.append(ScheduleBooking.project_id.in_(scope or {-1}))
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
    if scope is not None:
        member_ids = select(ProjectMember.user_id).where(
            ProjectMember.project_id.in_(scope or {-1}), ProjectMember.left_at.is_(None)
        )
        manager_ids = select(Project.manager_id).where(Project.id.in_(scope or {-1}))
        eligible_user_filters.append((User.id.in_(member_ids)) | (User.id.in_(manager_ids)) | (User.id == user.id))
    for eligible_user in db.scalars(select(User).where(*eligible_user_filters)).all():
        user_totals.setdefault(
            eligible_user.id,
            {"user_id": eligible_user.id, "user_name": eligible_user.name, "planned_hours": 0.0},
        )
    weekdays = sum((start_date + timedelta(days=index)).weekday() < 5 for index in range((end_date - start_date).days + 1))
    available = weekdays * settings.standard_work_hours
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
