from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.project import Project
from app.models.risk import RiskRecord
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.risk_repository import risk_repository
from app.schemas.risk import RiskHandleRequest
from app.services.notification_service import create_notification
from app.services.operation_log_service import log_operation
from app.services.project_service import manageable_project_ids
from app.utils.model import model_to_dict

OPEN_TASK_STATUSES = {"not_started", "running", "suspended"}
ACTIVE_SCHEDULE_STATUSES = {"pending", "confirmed", "changed", "running"}
RISK_TEAM_ROLES = {
    "project_manager",
    "department_manager",
    "functional_manager",
    "super_admin",
}


def _risk(
    fingerprint: str,
    risk_type: str,
    level: str,
    title: str,
    detail: str,
    *,
    project_id: int | None = None,
    task_id: int | None = None,
    user_id: int | None = None,
    due_at: datetime | None = None,
    source_data: dict | None = None,
) -> dict:
    return {
        "fingerprint": fingerprint,
        "risk_type": risk_type,
        "risk_level": level,
        "title": title,
        "detail": detail,
        "project_id": project_id,
        "task_id": task_id,
        "user_id": user_id,
        "due_at": due_at,
        "source_data": source_data,
    }


def _detect_task_and_project_risks(db: Session, scope: set[int] | None, now: datetime) -> list[dict]:
    result: list[dict] = []
    task_filters = [
        Task.status.in_(OPEN_TASK_STATUSES),
        Task.is_deleted.is_(False),
        Task.project_id.in_(
            select(Project.id).where(Project.is_deleted.is_(False))
        ),
    ]
    project_filters = [Project.is_deleted.is_(False), Project.status.notin_({"Completed", "Cancelled"})]
    if scope is not None:
        task_filters.append(Task.project_id.in_(scope or {-1}))
        project_filters.append(Project.id.in_(scope or {-1}))
    tasks = db.scalars(select(Task).where(*task_filters)).all()
    for task in tasks:
        if task.planned_end < now:
            overdue_days = max((now.date() - task.planned_end.date()).days, 1)
            result.append(
                _risk(
                    f"task_delay:{task.id}",
                    "task_delay",
                    "high" if overdue_days >= 3 else "medium",
                    f"任务延期：{task.name}",
                    f"计划结束时间已超过 {overdue_days} 天，任务仍未完成。",
                    project_id=task.project_id,
                    task_id=task.id,
                    user_id=task.owner_id,
                    due_at=task.planned_end,
                    source_data={"overdue_days": overdue_days, "status": task.status},
                )
            )
        if task.updated_at < now - timedelta(days=settings.risk_stale_days):
            stale_days = (now.date() - task.updated_at.date()).days
            result.append(
                _risk(
                    f"task_stale:{task.id}",
                    "long_unupdated",
                    "medium",
                    f"任务久未更新：{task.name}",
                    f"任务已连续 {stale_days} 天没有更新，请确认进展。",
                    project_id=task.project_id,
                    task_id=task.id,
                    user_id=task.owner_id,
                    source_data={"stale_days": stale_days},
                )
            )
    projects = db.scalars(select(Project).where(*project_filters)).all()
    for project in projects:
        if project.planned_end < now.date():
            overdue_days = max((now.date() - project.planned_end).days, 1)
            result.append(
                _risk(
                    f"project_delay:{project.id}",
                    "project_delay",
                    "critical" if overdue_days >= 7 else "high",
                    f"项目延期：{project.name}",
                    f"项目计划结束日期已超过 {overdue_days} 天。",
                    project_id=project.id,
                    user_id=project.manager_id,
                    due_at=datetime.combine(project.planned_end, time.max),
                    source_data={"overdue_days": overdue_days, "status": project.status},
                )
            )
    return result


def _detect_schedule_risks(db: Session, scope: set[int] | None, now: datetime) -> list[dict]:
    result: list[dict] = []
    filters = [
        ScheduleBooking.status.in_(ACTIVE_SCHEDULE_STATUSES),
        ScheduleBooking.project_id.in_(
            select(Project.id).where(Project.is_deleted.is_(False))
        ),
        ScheduleBooking.end_time >= datetime.combine(now.date(), time.min),
        ScheduleBooking.start_time < datetime.combine(now.date() + timedelta(days=31), time.min),
    ]
    if scope is not None:
        filters.append(ScheduleBooking.project_id.in_(scope or {-1}))
    schedules = db.scalars(
        select(ScheduleBooking).where(*filters).order_by(ScheduleBooking.user_id, ScheduleBooking.start_time)
    ).all()
    per_user: dict[int, list[ScheduleBooking]] = defaultdict(list)
    load: dict[tuple[int, date], Decimal] = defaultdict(lambda: Decimal("0"))
    load_projects: dict[tuple[int, date], set[int]] = defaultdict(set)
    for booking in schedules:
        per_user[booking.user_id].append(booking)
        load[(booking.user_id, booking.start_time.date())] += Decimal(str(booking.planned_hours))
        load_projects[(booking.user_id, booking.start_time.date())].add(booking.project_id)
    for user_id, bookings in per_user.items():
        for index, current in enumerate(bookings):
            for other in bookings[index + 1 :]:
                if other.start_time >= current.end_time:
                    break
                if other.end_time > current.start_time:
                    left_id, right_id = sorted((current.id, other.id))
                    result.append(
                        _risk(
                            f"schedule_conflict:{left_id}:{right_id}",
                            "staffing_conflict",
                            "high",
                            "人员排期冲突",
                            f"预约 #{left_id} 与预约 #{right_id} 的时间发生重叠。",
                            project_id=current.project_id,
                            user_id=user_id,
                            due_at=min(current.start_time, other.start_time),
                            source_data={"schedule_ids": [left_id, right_id]},
                        )
                    )
    standard = Decimal(str(settings.standard_work_hours))
    for (user_id, work_date), hours in load.items():
        if hours > standard:
            result.append(
                _risk(
                    f"workload_overload:{user_id}:{work_date.isoformat()}",
                    "workload_overload",
                    "high" if hours >= standard * Decimal("1.5") else "medium",
                    f"人员负载超限：{work_date.isoformat()}",
                    f"计划工时 {hours} 小时，超过每日标准工时 {standard} 小时。",
                    project_id=min(load_projects[(user_id, work_date)]),
                    user_id=user_id,
                    due_at=datetime.combine(work_date, time.max),
                    source_data={"planned_hours": float(hours), "available_hours": float(standard)},
                )
            )
    return result


def sync_risks(db: Session, user: User) -> dict:
    now = datetime.now()
    scope = manageable_project_ids(db, user)
    detected = _detect_task_and_project_risks(db, scope, now) + _detect_schedule_risks(db, scope, now)
    created = 0
    refreshed = 0
    reopened = 0
    for values in detected:
        existing = risk_repository.by_fingerprint(db, values["fingerprint"])
        if existing:
            existing.detail = values["detail"]
            existing.risk_level = values["risk_level"]
            existing.source_data = values["source_data"]
            existing.due_at = values["due_at"]
            existing.detected_at = now
            if existing.status == "resolved":
                existing.status = "open"
                existing.resolved_at = None
                existing.handled_by = None
                existing.handled_at = None
                existing.handling_note = "风险条件仍然存在，系统重新打开"
                recipients = {value for value in (existing.user_id,) if value}
                if existing.project_id:
                    manager_id = db.scalar(
                        select(Project.manager_id).where(Project.id == existing.project_id)
                    )
                    if manager_id:
                        recipients.add(manager_id)
                for recipient_id in recipients:
                    create_notification(
                        db,
                        recipient_id,
                        "risk_reopened",
                        existing.title or "项目风险重新打开",
                        existing.detail or "风险条件仍然存在，请重新处理。",
                        level="warning",
                        related_type="risk",
                        related_id=existing.id,
                    )
                reopened += 1
            refreshed += 1
            continue
        item = RiskRecord(**values, status="open", detected_at=now)
        db.add(item)
        db.flush()
        recipients = {value for value in (item.user_id,) if value}
        if item.project_id:
            manager_id = db.scalar(select(Project.manager_id).where(Project.id == item.project_id))
            if manager_id:
                recipients.add(manager_id)
        for recipient_id in recipients:
            create_notification(
                db,
                recipient_id,
                "risk_detected",
                item.title or "发现新的项目风险",
                item.detail or "请进入风险中心查看。",
                level="warning" if item.risk_level != "critical" else "error",
                related_type="risk",
                related_id=item.id,
            )
        created += 1
    log_operation(
        db,
        operator_id=user.id,
        module="risk",
        action="sync",
        object_type="risk_scan",
        object_id=now.isoformat(),
        after_data={"detected": len(detected), "created": created, "refreshed": refreshed, "reopened": reopened},
    )
    db.commit()
    return {"detected": len(detected), "created": created, "refreshed": refreshed, "reopened": reopened}


def list_risks(db: Session, user: User, page: int, page_size: int, **filters) -> dict:
    has_team_scope = bool(get_role_codes(db, user.id) & RISK_TEAM_ROLES)
    if not has_team_scope:
        filters["user_id"] = user.id
    items, total = risk_repository.list(
        db,
        page,
        page_size,
        viewer_id=user.id,
        visible_project_ids=(
            manageable_project_ids(db, user) if has_team_scope else None
        ),
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def handle_risk(db: Session, risk_id: int, payload: RiskHandleRequest, user: User) -> RiskRecord:
    if payload.status not in {"handling", "resolved", "ignored"}:
        raise bad_request("invalid risk status")
    item = risk_repository.get(db, risk_id)
    if not item:
        raise not_found("risk not found")
    has_team_scope = bool(get_role_codes(db, user.id) & RISK_TEAM_ROLES)
    if not has_team_scope:
        if item.user_id != user.id:
            raise forbidden("risk is outside your data scope")
    else:
        scope = manageable_project_ids(db, user)
        if (
            scope is not None
            and item.project_id is not None
            and item.project_id not in scope
            and item.user_id != user.id
        ):
            raise forbidden("risk is outside your data scope")
        if scope is not None and item.project_id is None and item.user_id != user.id:
            raise forbidden("risk is outside your data scope")
    before = model_to_dict(item)
    item.status = payload.status
    item.handled_by = user.id
    item.handled_at = datetime.now()
    item.handling_note = payload.handling_note
    item.resolved_at = datetime.now() if payload.status in {"resolved", "ignored"} else None
    log_operation(
        db,
        operator_id=user.id,
        module="risk",
        action="handle",
        object_type="risk_record",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def risk_stats(db: Session, user: User) -> dict:
    filters = []
    if not (get_role_codes(db, user.id) & RISK_TEAM_ROLES):
        filters.append(RiskRecord.user_id == user.id)
    else:
        scope = manageable_project_ids(db, user)
        if scope is not None:
            filters.append(
                (RiskRecord.project_id.in_(scope or {-1}))
                | (RiskRecord.user_id == user.id)
            )
    rows = db.execute(
        select(RiskRecord.status, RiskRecord.risk_level, func.count(RiskRecord.id))
        .where(*filters)
        .group_by(RiskRecord.status, RiskRecord.risk_level)
    ).all()
    by_status: dict[str, int] = defaultdict(int)
    by_level: dict[str, int] = defaultdict(int)
    for status, level, count in rows:
        by_status[status] += count
        by_level[level] += count
    return {
        "total": sum(by_status.values()),
        "open": by_status["open"] + by_status["handling"],
        "resolved": by_status["resolved"] + by_status["ignored"],
        "by_status": dict(by_status),
        "by_level": dict(by_level),
    }
