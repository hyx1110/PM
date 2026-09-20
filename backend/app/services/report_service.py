from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_role_codes
from app.models.project import Project
from app.models.risk import RiskRecord
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.report_repository import report_repository
from app.services.task_service import effective_status
from app.services.project_service import visible_project_ids
from app.services.visibility_service import dashboard_visibility_scopes, visible_schedule_user_ids
from app.services.work_calendar_service import count_workdays, is_workday
from app.utils.time import beijing_now


def process_report(db: Session, user: User, page: int, page_size: int, **filters):
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date and end_date and end_date < start_date:
        from app.core.exceptions import bad_request

        raise bad_request("结束日期不能早于开始日期")
    items, total = report_repository.process_report(
        db,
        page,
        page_size,
        visible_project_ids=visible_project_ids(db, user),
        **filters,
    )
    roles = get_role_codes(db, user.id)
    global_evaluator = bool(roles & {"super_admin", "department_manager"})
    for item in items:
        item["task_status"] = item["status"]
        item["effective_status"] = effective_status(item.pop("status"), item["planned_end"])
        item["can_evaluate"] = (
            (global_evaluator or item.pop("project_manager_id") == user.id)
            and item["project_status"] == "Completed"
            and item["task_status"] == "completed"
            and item["evaluation_id"] is None
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def workload_report(db: Session, user: User, start_date: date, end_date: date, department_id: int | None, user_id: int | None):
    _validate_range(start_date, end_date)
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
    roles, project_scope, schedule_user_ids = dashboard_visibility_scopes(db, user)
    project_filters = [Project.is_deleted.is_(False)]
    if project_scope is not None:
        project_filters.append(Project.id.in_(project_scope or {-1}))
    active_project_ids = select(Project.id).where(Project.is_deleted.is_(False))
    task_filters = [
        Task.is_deleted.is_(False),
        Task.project_id.in_(active_project_ids),
    ]
    schedule_filters = [
        ScheduleBooking.project_id.in_(active_project_ids),
        ScheduleBooking.task_id.in_(select(Task.id).where(Task.is_deleted.is_(False))),
    ]
    if project_scope is not None:
        task_filters.append(Task.project_id.in_(project_scope or {-1}))
        schedule_filters.append(ScheduleBooking.project_id.in_(project_scope or {-1}))
    scope_label = (
        "全部项目" if project_scope is None else
        "本人及全部下属相关项目" if "functional_manager" in roles else
        "本人负责或参与的项目"
    )
    now = beijing_now()
    today = now.date()
    project_total, project_running, project_completed, delayed_projects = db.execute(
        select(
            func.count(Project.id),
            func.coalesce(func.sum(case((Project.status == "Running", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Project.status == "Completed", 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                Project.planned_end < today,
                Project.status.notin_({"Completed", "Cancelled"}),
            ), 1), else_=0)), 0),
        ).where(*project_filters)
    ).one()
    delayed_tasks, total_tasks, completed_tasks = db.execute(
        select(
            func.coalesce(func.sum(case((and_(
                Task.planned_end < today,
                Task.status.notin_({"completed", "cancelled"}),
            ), 1), else_=0)), 0),
            func.count(Task.id),
            func.coalesce(func.sum(case((Task.status == "completed", 1), else_=0)), 0),
        ).where(*task_filters)
    ).one()
    pending = db.scalar(
        select(func.count(ScheduleBooking.id)).where(
            ScheduleBooking.user_id == user.id,
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time > now,
        )
    ) or 0
    pending_project_approvals = db.scalar(
        select(func.count(Project.id)).where(
            *([] if project_scope is None else [Project.approver_id == user.id]),
            Project.approval_status == "pending",
            Project.is_deleted.is_(False),
        )
    ) or 0
    my_task_filters = [
        Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user.id)),
        Task.project_id.in_(active_project_ids),
        Task.is_deleted.is_(False),
        Task.status.notin_({"completed", "cancelled"}),
    ]
    my_today_tasks, my_upcoming_tasks = db.execute(
        select(
            func.coalesce(func.sum(case((and_(
                Task.planned_start <= today,
                Task.planned_end >= today,
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                Task.planned_end > today,
                Task.planned_end <= today + timedelta(days=7),
            ), 1), else_=0)), 0),
        ).where(*my_task_filters)
    ).one()
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = datetime.combine(today + timedelta(days=1), datetime.min.time())
    risk_filters = [RiskRecord.status.in_({"open", "handling"})]
    if schedule_user_ids is not None:
        risk_filters.append(RiskRecord.user_id.in_(schedule_user_ids or {-1}))
    open_risks, critical_risks, today_risks = db.execute(
        select(
            func.count(RiskRecord.id),
            func.coalesce(func.sum(case((RiskRecord.risk_level == "critical", 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                RiskRecord.detected_at >= today_start,
                RiskRecord.detected_at < tomorrow_start,
            ), 1), else_=0)), 0),
        ).where(*risk_filters)
    ).one()
    trend_start = today - timedelta(days=13)
    trend_start_time = datetime.combine(trend_start, datetime.min.time())
    month_start = today.replace(day=1)
    next_month_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_start_time = datetime.combine(month_start, datetime.min.time())
    next_month_start_time = datetime.combine(next_month_start, datetime.min.time())
    counted_schedule_statuses = {"confirmed", "running", "completed"}
    visible_today_statuses = counted_schedule_statuses | {"pending", "changed"}
    today_count, recent_14_day_hours, month_hours = db.execute(
        select(
            func.coalesce(func.sum(case((and_(
                ScheduleBooking.status.in_(visible_today_statuses),
                ScheduleBooking.start_time >= today_start,
                ScheduleBooking.start_time < tomorrow_start,
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                ScheduleBooking.status.in_(counted_schedule_statuses),
                ScheduleBooking.start_time >= trend_start_time,
                ScheduleBooking.start_time < tomorrow_start,
            ), ScheduleBooking.planned_hours), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                ScheduleBooking.status.in_(counted_schedule_statuses),
                ScheduleBooking.start_time >= month_start_time,
                ScheduleBooking.start_time < next_month_start_time,
            ), ScheduleBooking.planned_hours), else_=0)), 0),
        ).where(*schedule_filters)
    ).one()
    active_user_filters = [User.status == "active", User.is_deleted.is_(False)]
    if project_scope is not None:
        from app.models.project import ProjectMember

        active_user_filters.append(or_(
            User.id.in_(select(ProjectMember.user_id).where(
                ProjectMember.project_id.in_(project_scope or {-1}),
                ProjectMember.left_at.is_(None),
            )),
            User.id.in_(select(ScheduleBooking.user_id).where(*schedule_filters)),
        ))
    active_users = db.scalar(select(func.count(User.id)).where(*active_user_filters)) or 0
    recent_14_day_workdays = count_workdays(db, trend_start, today)
    recent_14_day_capacity = active_users * recent_14_day_workdays * settings.standard_work_hours
    trend_rows = db.execute(
        select(
            func.date(ScheduleBooking.start_time).label("day"),
            func.sum(ScheduleBooking.planned_hours).label("hours"),
        )
        .where(
            *schedule_filters,
            ScheduleBooking.start_time >= trend_start_time,
            ScheduleBooking.start_time < tomorrow_start,
            ScheduleBooking.status.in_(counted_schedule_statuses),
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
        # Keep the legacy weekly fields for API compatibility. They now match
        # the 14-day chart and label instead of returning an unrelated week.
        "weekly_planned_hours": float(recent_14_day_hours),
        "recent_14_day_planned_hours": float(recent_14_day_hours),
        "monthly_planned_hours": float(month_hours),
        "weekly_utilization_rate": round(float(recent_14_day_hours) / recent_14_day_capacity * 100, 2) if recent_14_day_capacity else 0,
        "recent_14_day_utilization_rate": round(float(recent_14_day_hours) / recent_14_day_capacity * 100, 2) if recent_14_day_capacity else 0,
        "task_completion_rate": round(completed_tasks / total_tasks * 100, 2) if total_tasks else 0,
        "schedule_trend": trend,
        "planned_hours_scope": scope_label,
        "planned_hours_description": (
            f"统计范围：{scope_label}。按预约开始日期汇总已确认、执行中、已完成预约的计划工时；"
            "近14天为北京时间今天及之前13天，本月为自然月。待确认、拒绝、撤回和取消预约、"
            "个人请假培训安排不计入；项目预算、任务预计工时及实际工时不属于此统计。"
        ),
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
