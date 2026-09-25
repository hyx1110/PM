from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.execution import ExecutionRecord
from app.models.project import Project
from app.models.risk import RiskRecord
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.schedule_repository import schedule_repository
from app.services import project_service
from app.services.visibility_service import dashboard_visibility_scopes
from app.utils.time import beijing_now


COUNTED_SCHEDULE_STATUSES = {"confirmed", "running", "completed"}


def _number(value: Decimal | int | float | None) -> float:
    return round(float(value or 0), 2)


def _effective_status(status: str, planned_end: date, today: date) -> str:
    if status != "completed" and planned_end < today:
        return "delayed"
    return status


def _execution_aggregate():
    return (
        select(
            ExecutionRecord.task_id.label("task_id"),
            func.min(ExecutionRecord.actual_start).label("actual_start"),
            func.max(func.coalesce(ExecutionRecord.actual_end, ExecutionRecord.actual_start)).label("actual_end"),
            func.coalesce(func.sum(ExecutionRecord.actual_hours), 0).label("actual_hours"),
            func.count(ExecutionRecord.id).label("record_count"),
        )
        .where(ExecutionRecord.is_deleted.is_(False))
        .group_by(ExecutionRecord.task_id)
        .subquery()
    )


def _assignee_map(db: Session, task_ids: set[int]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = defaultdict(list)
    if not task_ids:
        return result
    rows = db.execute(
        select(TaskAssignee.task_id, User.id, User.name, User.employee_no)
        .join(User, User.id == TaskAssignee.user_id)
        .where(TaskAssignee.task_id.in_(task_ids), User.is_deleted.is_(False))
        .order_by(TaskAssignee.task_id, User.employee_no, User.id)
    ).all()
    for task_id, user_id, name, employee_no in rows:
        result[task_id].append({"id": user_id, "name": name, "employee_no": employee_no})
    return result


def _task_item(row, assignees: dict[int, list[dict]], today: date) -> dict:
    task, project_name, actual_start, actual_end, actual_hours, record_count = row
    estimated = _number(task.estimated_hours)
    actual = _number(actual_hours)
    owners = assignees.get(task.id, [])
    status = _effective_status(task.status, task.planned_end, today)
    if task.status == "completed":
        progress = 100
    elif estimated:
        progress = min(round(actual / estimated * 100), 95)
    else:
        progress = 0
    planned_days = (task.planned_end - task.planned_start).days + 1
    actual_days = (
        (actual_end - actual_start).days + 1
        if actual_start and actual_end
        else 0
    )
    deviation = round(actual - estimated, 2)
    deviation_rate = round(deviation / estimated * 100, 2) if estimated else 0
    variance = (
        "severe" if estimated and actual > estimated * 1.2 else
        "warning" if actual > estimated else
        "good"
    )
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project_name": project_name,
        "parent_id": task.parent_id,
        "name": task.name,
        "owner_ids": [owner["id"] for owner in owners],
        "owner_name": "、".join(owner["name"] for owner in owners) or "未分配",
        "planned_start": task.planned_start,
        "planned_end": task.planned_end,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "estimated_hours": estimated,
        "actual_hours": actual,
        "planned_days": planned_days,
        "actual_days": actual_days,
        "deviation_hours": deviation,
        "deviation_rate": deviation_rate,
        "variance": variance,
        "status": status,
        "progress": progress,
        "record_count": int(record_count or 0),
        "description": task.description,
        "remark": task.remark,
    }


def _pending_items(db: Session, user: User, now: datetime) -> list[dict]:
    items: list[dict] = []
    for project in project_service.list_pending_project_approvals(db, user):
        items.append({
            "id": f"project-{project['id']}",
            "source_id": project["id"],
            "type": "project_approval",
            "type_label": "项目审批",
            "title": project["name"],
            "project_id": project["id"],
            "project_name": project["name"],
            "applicant_name": project.get("creator_name") or project.get("manager_name") or "未知申请人",
            "content": f"项目周期 {project['planned_start']} 至 {project['planned_end']}，预算 {_number(project.get('budget_hours'))}h",
            "created_at": project.get("created_at"),
            "status": "pending",
            "actionable": True,
        })
    for request in project_service.list_pending_resource_requests(db, user):
        changes = []
        if request.get("requested_hours"):
            changes.append(f"追加 {_number(request['requested_hours'])}h")
        if request.get("add_member_ids"):
            changes.append(f"新增 {len(request['add_member_ids'])} 人")
        if request.get("remove_member_ids"):
            changes.append(f"移除 {len(request['remove_member_ids'])} 人")
        items.append({
            "id": f"resource-{request['id']}",
            "source_id": request["id"],
            "type": "resource_approval",
            "type_label": "资源审批",
            "title": request.get("project_name") or "项目资源申请",
            "project_id": request["project_id"],
            "project_name": request.get("project_name"),
            "applicant_name": request.get("requester_name") or "未知申请人",
            "content": "、".join(changes) + (f"；{request['reason']}" if request.get("reason") else ""),
            "created_at": request.get("created_at"),
            "status": "pending",
            "actionable": True,
        })
    for booking in schedule_repository.list_pending_for_user(db, user.id, 100):
        if booking["end_time"] <= now:
            continue
        items.append({
            "id": f"booking-{booking['id']}",
            "source_id": booking["id"],
            "type": "booking",
            "type_label": "预约确认",
            "title": booking.get("task_name") or "人力预约",
            "project_id": booking["project_id"],
            "project_name": booking.get("project_name"),
            "task_id": booking["task_id"],
            "applicant_name": booking.get("created_by_name") or "未知申请人",
            "booking_user_name": booking.get("user_name"),
            "content": f"{booking['start_time']:%m-%d %H:%M} 至 {booking['end_time']:%H:%M}，{_number(booking['planned_hours'])}h",
            "start_time": booking["start_time"],
            "end_time": booking["end_time"],
            "planned_hours": _number(booking["planned_hours"]),
            "created_at": booking.get("created_at"),
            "status": booking["status"],
            "actionable": True,
        })
    return sorted(items, key=lambda item: item.get("created_at") or now)


def dashboard_workbench(db: Session, user: User) -> dict:
    now = beijing_now()
    today = now.date()
    roles, project_scope, schedule_user_ids = dashboard_visibility_scopes(db, user)

    project_filters = [Project.is_deleted.is_(False)]
    if project_scope is not None:
        project_filters.append(Project.id.in_(project_scope or {-1}))
    approved_project_filters = [*project_filters, Project.approval_status == "approved"]
    visible_project_ids_query = select(Project.id).where(*project_filters)
    approved_project_ids_query = select(Project.id).where(*approved_project_filters)
    task_filters = [
        Task.is_deleted.is_(False),
        Task.project_id.in_(visible_project_ids_query),
    ]
    execution_agg = _execution_aggregate()

    project_priority = case(
        (and_(Project.status != "completed", Project.planned_end < today), 0),
        (Project.status == "running", 1),
        (Project.status == "not_started", 2),
        else_=3,
    )
    manager = aliased(User)
    project_rows = db.execute(
        select(Project, manager.name.label("manager_name"))
        .join(manager, manager.id == Project.manager_id)
        .where(*approved_project_filters)
        .order_by(project_priority, Project.updated_at.desc(), Project.planned_end.asc())
        .limit(5)
    ).all()
    timeline_project_ids = [project.id for project, _ in project_rows]

    task_select = select(
        Task,
        Project.name.label("project_name"),
        execution_agg.c.actual_start,
        execution_agg.c.actual_end,
        func.coalesce(execution_agg.c.actual_hours, 0).label("actual_hours"),
        func.coalesce(execution_agg.c.record_count, 0).label("record_count"),
    ).join(Project, Project.id == Task.project_id).outerjoin(
        execution_agg, execution_agg.c.task_id == Task.id
    )

    timeline_rows = db.execute(
        task_select.where(
            Task.project_id.in_(timeline_project_ids or {-1}),
            Task.is_deleted.is_(False),
        ).order_by(Task.project_id, Task.planned_start, Task.parent_id, Task.id)
    ).all()

    my_rows = db.execute(
        task_select.where(
            *task_filters,
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user.id)),
        ).order_by(
            case(
                (and_(Task.status != "completed", Task.planned_end < today), 0),
                (Task.status == "running", 1),
                (Task.status == "not_started", 2),
                else_=3,
            ),
            Task.planned_end,
            Task.id.desc(),
        ).limit(40)
    ).all()

    comparison_rows = db.execute(
        task_select.where(
            *task_filters,
            or_(
                func.coalesce(execution_agg.c.actual_hours, 0) > 0,
                and_(Task.status != "completed", Task.planned_end < today),
            ),
        ).order_by(
            (func.coalesce(execution_agg.c.actual_hours, 0) - Task.estimated_hours).desc(),
            Task.planned_end.asc(),
        ).limit(12)
    ).all()

    all_task_ids = {
        row[0].id
        for rows in (timeline_rows, my_rows, comparison_rows)
        for row in rows
    }
    assignees = _assignee_map(db, all_task_ids)
    task_cache = {
        row[0].id: _task_item(row, assignees, today)
        for rows in (timeline_rows, my_rows, comparison_rows)
        for row in rows
    }

    project_tasks: dict[int, list[dict]] = defaultdict(list)
    for row in timeline_rows:
        project_tasks[row[0].project_id].append(task_cache[row[0].id])

    timeline: list[dict] = []
    project_health: list[dict] = []
    for project, manager_name in project_rows:
        tasks = project_tasks.get(project.id, [])
        parent_task_ids = {item["parent_id"] for item in tasks if item["parent_id"]}
        progress_tasks = [item for item in tasks if item["id"] not in parent_task_ids] or tasks
        estimated_total = sum(item["estimated_hours"] for item in progress_tasks)
        completed_weight = sum(
            item["estimated_hours"] for item in progress_tasks if item["status"] == "completed"
        )
        completed_count = sum(item["status"] == "completed" for item in progress_tasks)
        progress = (
            round(completed_weight / estimated_total * 100)
            if estimated_total else
            round(completed_count / len(progress_tasks) * 100) if progress_tasks else 0
        )
        task_actual_starts = [item["actual_start"] for item in tasks if item["actual_start"]]
        task_actual_ends = [item["actual_end"] for item in tasks if item["actual_end"]]
        project_status = _effective_status(project.status, project.planned_end, today)
        delayed_task_count = sum(item["status"] == "delayed" for item in tasks)
        overrun_task_count = sum(item["variance"] in {"warning", "severe"} for item in tasks)
        days_to_due = (project.planned_end - today).days
        if project_status == "delayed":
            health_status, reason = "delayed", f"计划结束已超期 {abs(days_to_due)} 天"
        elif delayed_task_count:
            health_status, reason = "risk", f"{delayed_task_count} 个任务已延期"
        elif overrun_task_count:
            health_status, reason = "attention", f"{overrun_task_count} 个任务实际工时超出预计"
        elif project.status != "completed" and 0 <= days_to_due <= 7:
            health_status, reason = "attention", f"距离计划结束还有 {days_to_due} 天"
        else:
            health_status, reason = "normal", "项目按计划推进"
        timeline_item = {
            "id": project.id,
            "code": project.code,
            "name": project.name,
            "manager_name": manager_name,
            "planned_start": project.planned_start,
            "planned_end": project.planned_end,
            "actual_start": project.actual_start or (min(task_actual_starts) if task_actual_starts else None),
            "actual_end": project.actual_end or (max(task_actual_ends) if task_actual_ends else None),
            "status": project_status,
            "progress": progress,
            "task_count": len(progress_tasks),
            "completed_task_count": completed_count,
            "tasks": tasks[:6],
        }
        timeline.append(timeline_item)
        project_health.append({
            "project_id": project.id,
            "project_name": project.name,
            "status": health_status,
            "reason": reason,
            "progress": progress,
        })

    pending_items = _pending_items(db, user, now)

    risk_filters = [RiskRecord.status.in_({"open", "handling"})]
    if project_scope is not None:
        risk_filters.append(or_(
            RiskRecord.project_id.in_(project_scope or {-1}),
            RiskRecord.user_id.in_(schedule_user_ids or {-1}),
            RiskRecord.user_id == user.id,
        ))
    risk_rows = db.execute(
        select(RiskRecord, Project.name, Task.name)
        .outerjoin(Project, Project.id == RiskRecord.project_id)
        .outerjoin(Task, Task.id == RiskRecord.task_id)
        .where(*risk_filters)
        .order_by(
            case((RiskRecord.risk_level == "critical", 0), (RiskRecord.risk_level == "high", 1), else_=2),
            RiskRecord.detected_at.desc(),
        )
        .limit(8)
    ).all()
    risk_alerts = [
        {
            "id": f"risk-{risk.id}",
            "type": "risk_record",
            "severity": "danger" if risk.risk_level in {"critical", "high"} else "warning",
            "title": risk.title or risk.detail or "项目风险待处理",
            "detail": risk.detail,
            "project_id": risk.project_id,
            "project_name": project_name,
            "task_id": risk.task_id,
            "task_name": task_name,
            "occurred_at": risk.detected_at,
        }
        for risk, project_name, task_name in risk_rows
    ]
    existing_alert_keys = {(item.get("type"), item.get("task_id")) for item in risk_alerts}
    for item in [task_cache[row[0].id] for row in comparison_rows]:
        if item["status"] == "delayed" and ("delayed_task", item["id"]) not in existing_alert_keys:
            risk_alerts.append({
                "id": f"delayed-task-{item['id']}",
                "type": "delayed_task",
                "severity": "danger",
                "title": f"{item['name']} 已延期 {(today - item['planned_end']).days} 天",
                "detail": f"计划结束日为 {item['planned_end']}，当前任务仍未完成。",
                "project_id": item["project_id"],
                "project_name": item["project_name"],
                "task_id": item["id"],
                "task_name": item["name"],
                "occurred_at": datetime.combine(item["planned_end"], datetime.min.time()),
            })
        elif item["variance"] in {"warning", "severe"} and ("overrun_task", item["id"]) not in existing_alert_keys:
            risk_alerts.append({
                "id": f"overrun-task-{item['id']}",
                "type": "overrun_task",
                "severity": "danger" if item["variance"] == "severe" else "warning",
                "title": f"{item['name']} 实际工时超出预计 {item['deviation_hours']}h",
                "detail": f"预计 {item['estimated_hours']}h，当前累计实际 {item['actual_hours']}h。",
                "project_id": item["project_id"],
                "project_name": item["project_name"],
                "task_id": item["id"],
                "task_name": item["name"],
                "occurred_at": datetime.combine(item["actual_end"], datetime.min.time()) if item.get("actual_end") else now,
            })
    for item in pending_items:
        created_at = item.get("created_at")
        if isinstance(created_at, datetime) and created_at < now - timedelta(hours=24):
            risk_alerts.append({
                "id": f"pending-overdue-{item['id']}",
                "type": "pending_overdue",
                "severity": "warning",
                "title": f"{item['type_label']}已等待超过 24 小时",
                "detail": f"{item['title']} · 申请人 {item['applicant_name']}",
                "project_id": item.get("project_id"),
                "project_name": item.get("project_name"),
                "task_id": item.get("task_id"),
                "task_name": item.get("title") if item.get("task_id") else None,
                "occurred_at": created_at,
            })
    risk_alerts = risk_alerts[:12]

    trend_start = today - timedelta(days=30)
    trend_start_time = datetime.combine(trend_start, datetime.min.time())
    tomorrow_start = datetime.combine(today + timedelta(days=1), datetime.min.time())
    schedule_filters = [
        ScheduleBooking.project_id.in_(approved_project_ids_query),
        ScheduleBooking.status.in_(COUNTED_SCHEDULE_STATUSES),
        ScheduleBooking.start_time >= trend_start_time,
        ScheduleBooking.start_time < tomorrow_start,
    ]
    planned_rows = db.execute(
        select(
            func.date(ScheduleBooking.start_time),
            func.coalesce(func.sum(ScheduleBooking.planned_hours), 0),
        ).where(*schedule_filters).group_by(func.date(ScheduleBooking.start_time))
    ).all()
    actual_rows = db.execute(
        select(
            ExecutionRecord.actual_start,
            func.coalesce(func.sum(ExecutionRecord.actual_hours), 0),
        )
        .join(Task, Task.id == ExecutionRecord.task_id)
        .where(
            ExecutionRecord.is_deleted.is_(False),
            ExecutionRecord.actual_start >= trend_start,
            ExecutionRecord.actual_start <= today,
            Task.is_deleted.is_(False),
            Task.project_id.in_(approved_project_ids_query),
        )
        .group_by(ExecutionRecord.actual_start)
    ).all()
    planned_map = {str(day): _number(hours) for day, hours in planned_rows}
    actual_map = {str(day): _number(hours) for day, hours in actual_rows}
    workhour_trend = [
        {
            "date": (trend_start + timedelta(days=index)).isoformat(),
            "planned_hours": planned_map.get((trend_start + timedelta(days=index)).isoformat(), 0),
            "actual_hours": actual_map.get((trend_start + timedelta(days=index)).isoformat(), 0),
        }
        for index in range(31)
    ]

    total_tasks, completed_tasks = db.execute(
        select(
            func.count(Task.id),
            func.coalesce(func.sum(case((Task.status == "completed", 1), else_=0)), 0),
        ).where(*task_filters)
    ).one()
    running_projects = db.scalar(
        select(func.count(Project.id)).where(
            *approved_project_filters,
            Project.status == "running",
            Project.planned_end >= today,
        )
    ) or 0
    due_this_week = db.scalar(
        select(func.count(Project.id)).where(
            *approved_project_filters,
            Project.status != "completed",
            Project.planned_end >= today,
            Project.planned_end <= today + timedelta(days=7),
        )
    ) or 0
    delayed_project_ids = set(db.scalars(
        select(Project.id).where(
            *approved_project_filters,
            Project.status != "completed",
            Project.planned_end < today,
        )
    ).all())
    delayed_task_project_ids = set(db.scalars(
        select(Task.project_id).where(
            *task_filters,
            Task.status != "completed",
            Task.planned_end < today,
        ).distinct()
    ).all())
    overrun_task_rows = db.execute(
        select(Task.id, Task.project_id)
        .outerjoin(execution_agg, execution_agg.c.task_id == Task.id)
        .where(
            *task_filters,
            func.coalesce(execution_agg.c.actual_hours, 0) > Task.estimated_hours,
        ).distinct()
    ).all()
    overrun_task_ids = {task_id for task_id, _ in overrun_task_rows}
    overrun_project_ids = {project_id for _, project_id in overrun_task_rows}
    risk_project_ids = delayed_project_ids | delayed_task_project_ids | overrun_project_ids
    pending_approval_count = sum(item["type"] != "booking" for item in pending_items)
    pending_schedule_count, pending_schedule_today = db.execute(
        select(
            func.count(ScheduleBooking.id),
            func.coalesce(func.sum(case((ScheduleBooking.start_time < tomorrow_start, 1), else_=0)), 0),
        ).where(
            ScheduleBooking.user_id == user.id,
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time > now,
        )
    ).one()
    my_pending_task_count, my_priority_task_count = db.execute(
        select(
            func.count(Task.id),
            func.coalesce(func.sum(case((Task.planned_start <= today, 1), else_=0)), 0),
        ).where(
            *task_filters,
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user.id)),
            Task.status != "completed",
        )
    ).one()
    pending_action_count = pending_approval_count + int(pending_schedule_count or 0)
    pending_count = pending_action_count + int(my_pending_task_count or 0)
    pending_today = pending_approval_count + int(pending_schedule_today or 0) + int(my_priority_task_count or 0)
    scope_label = (
        "全部项目与人员" if project_scope is None else
        "本人及全部下属相关项目" if "functional_manager" in roles else
        "本人负责、参与或执行的项目"
    )
    overview = {
        "running_projects": int(running_projects),
        "due_this_week": int(due_this_week),
        "task_completion_rate": round(float(completed_tasks or 0) / float(total_tasks or 1) * 100, 1) if total_tasks else 0,
        "completed_tasks": int(completed_tasks or 0),
        "total_tasks": int(total_tasks or 0),
        "pending_count": pending_count,
        "pending_today": int(pending_today),
        "pending_action_count": pending_action_count,
        "pending_task_count": int(my_pending_task_count or 0),
        "risk_projects": len(risk_project_ids),
        "delayed_projects": len(delayed_project_ids),
        "overrun_tasks": len(overrun_task_ids),
    }
    return {
        "generated_at": now,
        "scope_label": scope_label,
        "overview": overview,
        "timeline": timeline,
        "execution_comparison": [task_cache[row[0].id] for row in comparison_rows],
        "pending_items": pending_items,
        "my_tasks": [task_cache[row[0].id] for row in my_rows],
        "risk_alerts": risk_alerts,
        "workhour_trend": workhour_trend,
        "project_health": project_health,
    }
