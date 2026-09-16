from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.project import ProjectMember
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.task_repository import task_repository
from app.schemas.task import TASK_STATUSES, TASK_TYPES, TaskCreate, TaskUpdate
from app.services.operation_log_service import log_operation
from app.services.notification_service import create_notification
from app.services.project_service import (
    assert_project_approved,
    assert_project_manageable,
    assert_project_visible,
)
from app.utils.model import model_to_dict
from app.utils.time import beijing_now


def effective_status(task_status: str, planned_end: datetime, now: datetime | None = None) -> str:
    current = now or beijing_now()
    if current > planned_end and task_status not in {"completed", "cancelled"}:
        return "delayed"
    return task_status


def _validate_owners(db: Session, project_id: int, owner_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(owner_ids))
    if not unique_ids:
        raise bad_request("请至少选择一名任务负责人")
    active_member_ids = set(
        db.scalars(
            select(ProjectMember.user_id)
            .join(User, User.id == ProjectMember.user_id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.left_at.is_(None),
                User.status == "active",
                User.is_deleted.is_(False),
            )
        ).all()
    )
    missing = set(unique_ids) - active_member_ids
    if missing:
        raise bad_request("所有任务负责人都必须是当前项目的有效成员")
    return unique_ids


def _assignee_ids(db: Session, task_id: int) -> list[int]:
    return list(db.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == task_id)).all())


def _assert_task_assignee(db: Session, task: Task, user: User) -> None:
    if user.id not in _assignee_ids(db, task.id):
        raise forbidden("只有任务负责人可以编辑或删除该任务")


def list_tasks(db: Session, user: User, page: int, page_size: int, project_id: int | None, owner_id: int | None, status: str | None, department_id: int | None = None, organization_id: int | None = None, employee_no: str | None = None, owner_name: str | None = None):
    items, total = task_repository.list(
        db,
        page,
        page_size,
        project_id,
        owner_id,
        status,
        department_id,
        organization_id,
        employee_no,
        owner_name,
    )
    for item in items:
        item["effective_status"] = effective_status(item["status"], item["planned_end"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_my_tasks(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    status: str | None,
):
    items, total = task_repository.list(
        db,
        page,
        page_size,
        owner_id=user.id,
        status=status,
    )
    for item in items:
        item["effective_status"] = effective_status(
            item["status"], item["planned_end"]
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _active_booking_hours(db: Session, task_id: int) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(
            ScheduleBooking.task_id == task_id,
            ScheduleBooking.status.in_(
                {"pending", "confirmed", "changed", "running", "completed"}
            ),
        )
    ) or Decimal("0")


def task_detail(db: Session, task_id: int, user: User) -> dict:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    assert_project_visible(db, task.project_id, user)
    match = task_repository.detail(db, task_id)
    match["effective_status"] = effective_status(match["status"], match["planned_end"])
    return match


def _validate_parent(db: Session, project_id: int, parent_id: int | None, current_task_id: int | None = None) -> None:
    if not parent_id:
        return
    parent = task_repository.get(db, parent_id)
    if not parent or parent.project_id != project_id:
        raise bad_request("parent task must belong to the same project")
    cursor = parent
    while cursor:
        if current_task_id and cursor.id == current_task_id:
            raise bad_request("task hierarchy cannot contain a cycle")
        cursor = task_repository.get(db, cursor.parent_id) if cursor.parent_id else None


def create_task(db: Session, payload: TaskCreate, user: User) -> Task:
    assert_project_manageable(db, payload.project_id, user)
    assert_project_approved(db, payload.project_id)
    owner_ids = _validate_owners(db, payload.project_id, payload.owner_ids)
    _validate_parent(db, payload.project_id, payload.parent_id)
    values = payload.model_dump(exclude={"owner_ids"})
    task = Task(**values, owner_id=owner_ids[0], priority="medium")
    db.add(task)
    db.flush()
    for owner_id in owner_ids:
        db.add(TaskAssignee(task_id=task.id, user_id=owner_id))
        if owner_id != user.id:
            create_notification(
                db,
                owner_id,
                "task_assigned",
                "你收到了一项新任务",
                f"任务“{task.name}”已分配给你，请关注计划时间和预计工时。",
                related_type="task",
                related_id=task.id,
            )
    log_operation(db, operator_id=user.id, module="task", action="create", object_type="task", object_id=task.id, after_data=model_to_dict(task))
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate, user: User) -> Task:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    _assert_task_assignee(db, task, user)
    before = model_to_dict(task)
    values = payload.model_dump(exclude_unset=True)
    owner_ids = values.pop("owner_ids", None)
    normalized_owner_ids = _validate_owners(db, task.project_id, owner_ids) if owner_ids is not None else _assignee_ids(db, task.id)
    _validate_parent(db, task.project_id, values.get("parent_id", task.parent_id), task.id)
    planned_start = values.get("planned_start", task.planned_start)
    planned_end = values.get("planned_end", task.planned_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    if values.get("task_type") and values["task_type"] not in TASK_TYPES:
        raise bad_request("invalid task type")
    if values.get("status") and values["status"] not in TASK_STATUSES:
        raise bad_request("invalid task status")
    if "estimated_hours" in values:
        booked_hours = _active_booking_hours(db, task.id)
        if values["estimated_hours"] < booked_hours:
            raise bad_request(
                f"当前任务已有 {booked_hours} 小时有效预约，预计工时不能小于有效预约工时"
            )
    previous_owner_ids = set(_assignee_ids(db, task.id))
    owner_changed = set(normalized_owner_ids) != previous_owner_ids
    time_changed = any(
        key in values and values[key] != getattr(task, key)
        for key in {"planned_start", "planned_end"}
    )
    for key, value in values.items():
        setattr(task, key, value)
    if owner_changed:
        db.query(TaskAssignee).filter(TaskAssignee.task_id == task.id).delete(synchronize_session=False)
        for owner_id in normalized_owner_ids:
            db.add(TaskAssignee(task_id=task.id, user_id=owner_id))
        task.owner_id = normalized_owner_ids[0]
    db.flush()
    if owner_changed:
        for owner_id in previous_owner_ids - set(normalized_owner_ids):
            create_notification(db, owner_id, "task_owner_changed", "任务负责人已变更", f"你已不再负责任务“{task.name}”。", level="warning", related_type="task", related_id=task.id)
        for owner_id in set(normalized_owner_ids) - previous_owner_ids:
            create_notification(db, owner_id, "task_owner_changed", "任务负责人已变更", f"任务“{task.name}”现已由你负责。", level="warning", related_type="task", related_id=task.id)
    if time_changed:
        for owner_id in normalized_owner_ids:
            create_notification(db, owner_id, "task_time_changed", "任务计划时间发生变化", f"任务“{task.name}”的计划时间已调整为 {task.planned_start:%Y-%m-%d %H:%M} 至 {task.planned_end:%Y-%m-%d %H:%M}。", level="warning", related_type="task", related_id=task.id)
    log_operation(db, operator_id=user.id, module="task", action="update", object_type="task", object_id=task.id, before_data=before, after_data=model_to_dict(task))
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int, user: User) -> None:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    _assert_task_assignee(db, task, user)
    if task.status not in {"not_started", "cancelled"}:
        raise bad_request("only not-started or cancelled tasks can be deleted")
    if db.scalar(
        select(Task.id)
        .where(Task.parent_id == task_id, Task.is_deleted.is_(False))
        .limit(1)
    ):
        raise conflict("delete child tasks before deleting this task", 40931)

    if db.scalar(
        select(ScheduleBooking.id)
        .where(
            ScheduleBooking.task_id == task_id,
            ScheduleBooking.status.in_(
                {"pending", "confirmed", "changed", "running"}
            ),
        )
        .limit(1)
    ):
        raise conflict(
            "cancel or complete the task's active schedules before deleting it",
            40932,
            {"dependencies": ["active schedules"]},
        )

    before = model_to_dict(task)
    task.is_deleted = True
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="task",
        action="delete",
        object_type="task",
        object_id=task_id,
        before_data=before,
    )
    db.commit()
