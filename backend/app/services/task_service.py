from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.execution import ExecutionRecord
from app.models.project import Project, ProjectMember
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.project_repository import booked_schedule_predicate
from app.repositories.task_repository import task_repository
from app.schemas.task import TASK_FILTER_STATUSES, TaskCreate, TaskUpdate
from app.services.operation_log_service import log_operation
from app.services.notification_service import create_notification
from app.services.project_service import (
    assert_project_approved,
    assert_project_manageable,
    assert_project_visible,
    manageable_project_ids,
    visible_project_ids,
)
from app.services.visibility_service import has_global_project_access
from app.services.schedule_lifecycle_service import synchronize_schedule_statuses
from app.services.status_sync_service import (
    synchronize_parent_status,
    synchronize_project_status,
    synchronize_task_status,
)
from app.utils.model import model_to_dict
from app.utils.time import beijing_today

def effective_status(task_status: str, planned_end: date, now: date | None = None) -> str:
    current = now or beijing_today()
    if current > planned_end and task_status != "completed":
        return "delayed"
    return task_status


def _validate_owners(db: Session, project_id: int, owner_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(owner_ids))
    if not unique_ids:
        raise bad_request("请至少选择一名任务项目成员")
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
        raise bad_request("所有任务项目成员都必须是当前项目的有效成员")
    return unique_ids


def _assignee_ids(db: Session, task_id: int) -> list[int]:
    return list(db.scalars(select(TaskAssignee.user_id).where(TaskAssignee.task_id == task_id)).all())


def _assert_task_assignee(db: Session, task: Task, user: User) -> None:
    if user.id not in _assignee_ids(db, task.id):
        raise forbidden("只有任务项目成员可以编辑或删除该任务")


def list_tasks(db: Session, user: User, page: int, page_size: int, project_id: int | None, owner_id: int | None, status: str | None, department_id: int | None = None, organization_id: int | None = None, employee_no: str | None = None, owner_name: str | None = None, managed_project_scope: bool = False, personnel_keyword: str | None = None, organization_keyword: str | None = None):
    if status and status not in TASK_FILTER_STATUSES:
        raise bad_request("invalid task status filter")
    scope = manageable_project_ids(db, user) if managed_project_scope else visible_project_ids(db, user)
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
        visible_project_ids=scope,
        personnel_keyword=personnel_keyword,
        organization_keyword=organization_keyword,
    )
    global_access = has_global_project_access(db, user)
    for item in items:
        item["effective_status"] = effective_status(item["status"], item["planned_end"])
        _add_permissions(item, user, global_access)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_my_tasks(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    status: str | None,
):
    if status and status not in TASK_FILTER_STATUSES:
        raise bad_request("invalid task status filter")
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
        _add_permissions(item, user, has_global_project_access(db, user))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _active_booking_hours(db: Session, task_id: int) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(
            ScheduleBooking.task_id == task_id,
            booked_schedule_predicate(),
        )
    ) or Decimal("0")


def task_detail(db: Session, task_id: int, user: User) -> dict:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    project = db.get(Project, task.project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    assert_project_visible(db, task.project_id, user)
    return task_response(db, task_id, user)


def _add_permissions(item: dict, user: User, global_access: bool) -> None:
    can_manage = global_access or item.get("project_manager_id") == user.id
    item["can_manage"] = can_manage
    item["can_edit"] = can_manage or user.id in item.get("owner_ids", []) or item.get("owner_id") == user.id
    item["can_delete"] = can_manage


def task_response(db: Session, task_id: int, user: User | None = None) -> dict:
    """Build an enriched response after access has already been checked."""
    match = task_repository.detail(db, task_id)
    if not match:
        raise not_found("task not found")
    match["effective_status"] = effective_status(match["status"], match["planned_end"])
    if user:
        _add_permissions(match, user, has_global_project_access(db, user))
    return match


def _validate_parent(db: Session, project_id: int, parent_id: int | None, current_task_id: int | None = None) -> Task | None:
    if not parent_id:
        return None
    parent = task_repository.get(db, parent_id)
    if not parent or parent.project_id != project_id:
        raise bad_request("parent task must belong to the same project")
    if parent.status == "completed":
        raise bad_request("不能在已完成的任务下新增或移动子任务")
    if current_task_id is None and db.scalar(
        select(ExecutionRecord.id).where(
            ExecutionRecord.task_id == parent.id,
            ExecutionRecord.is_deleted.is_(False),
        ).limit(1)
    ):
        raise bad_request("已有执行记录的任务不能再作为汇总任务，请先删除执行记录")
    if current_task_id is None and db.scalar(
        select(ScheduleBooking.id).where(
            ScheduleBooking.task_id == parent.id,
            ScheduleBooking.status.notin_({"rejected", "cancelled", "withdrawn"}),
        ).limit(1)
    ):
        raise bad_request("已有有效预约记录的任务不能再作为汇总任务")
    cursor = parent
    while cursor:
        if current_task_id and cursor.id == current_task_id:
            raise bad_request("task hierarchy cannot contain a cycle")
        cursor = task_repository.get(db, cursor.parent_id) if cursor.parent_id else None
    return parent


def _validate_assignees_with_parent(
    db: Session,
    parent: Task | None,
    owner_ids: list[int],
) -> None:
    if not parent:
        return
    parent_owner_ids = set(_assignee_ids(db, parent.id))
    invalid_ids = set(owner_ids) - parent_owner_ids
    if invalid_ids:
        raise bad_request("子任务的项目成员只能从父任务的项目成员中选择")


def _validate_estimated_hours(
    db: Session,
    project_id: int,
    parent_id: int | None,
    estimated_hours: Decimal,
    current_task_id: int | None = None,
) -> None:
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    sibling_filters = [
        Task.project_id == project_id,
        Task.parent_id == parent_id if parent_id is not None else Task.parent_id.is_(None),
        Task.is_deleted.is_(False),
    ]
    if current_task_id:
        sibling_filters.append(Task.id != current_task_id)
    sibling_hours = db.scalar(
        select(func.coalesce(func.sum(Task.estimated_hours), 0)).where(*sibling_filters)
    ) or Decimal("0")
    limit = project.budget_hours
    if parent_id:
        parent = task_repository.get(db, parent_id)
        if not parent:
            raise not_found("parent task not found")
        limit = parent.estimated_hours
    if sibling_hours + estimated_hours > limit:
        scope = "父任务" if parent_id else "项目"
        raise bad_request(
            f"同级任务预计工时合计不能超过{scope}工时：已分配 {sibling_hours} 小时，"
            f"本次 {estimated_hours} 小时，可用上限 {limit} 小时"
        )
    if current_task_id:
        child_hours = db.scalar(
            select(func.coalesce(func.sum(Task.estimated_hours), 0)).where(
                Task.parent_id == current_task_id,
                Task.is_deleted.is_(False),
            )
        ) or Decimal("0")
        if child_hours > estimated_hours:
            raise bad_request(
                f"当前任务的直接子任务预计工时合计为 {child_hours} 小时，"
                f"任务预计工时不能低于该值"
            )


def _validate_task_window(
    db: Session,
    project_id: int,
    planned_start: date,
    planned_end: date,
    parent_id: int | None = None,
    current_task_id: int | None = None,
) -> None:
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    if planned_start < project.planned_start or planned_end > project.planned_end:
        raise bad_request("任务计划时间必须位于项目计划日期范围内")
    if parent_id:
        parent = task_repository.get(db, parent_id)
        if not parent:
            raise not_found("parent task not found")
        if planned_start < parent.planned_start or planned_end > parent.planned_end:
            raise bad_request("子任务计划时间必须位于父任务计划日期范围内")
    if current_task_id and db.scalar(
        select(Task.id).where(
            Task.parent_id == current_task_id,
            Task.is_deleted.is_(False),
            or_(
                Task.planned_start < planned_start,
                Task.planned_end > planned_end,
            ),
        ).limit(1)
    ):
        raise bad_request("任务计划时间不能排除已有子任务的计划日期")


def create_task(db: Session, payload: TaskCreate, user: User) -> Task:
    assert_project_manageable(db, payload.project_id, user)
    assert_project_approved(db, payload.project_id)
    owner_ids = _validate_owners(db, payload.project_id, payload.owner_ids)
    parent = _validate_parent(db, payload.project_id, payload.parent_id)
    _validate_assignees_with_parent(db, parent, owner_ids)
    _validate_estimated_hours(
        db, payload.project_id, payload.parent_id, payload.estimated_hours
    )
    _validate_task_window(
        db,
        payload.project_id,
        payload.planned_start,
        payload.planned_end,
        payload.parent_id,
    )
    values = payload.model_dump(exclude={"owner_ids"})
    task = Task(
        **values,
        owner_id=owner_ids[0],
        priority="medium",
        status="not_started",
    )
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
    project = db.get(Project, task.project_id)
    can_manage = bool(project and (project.manager_id == user.id or has_global_project_access(db, user)))
    values = payload.model_dump(exclude_unset=True)
    if not can_manage:
        _assert_task_assignee(db, task, user)
        if set(values) - {"remark"}:
            raise forbidden("任务项目成员可修改备注并填写执行记录；核心计划字段仅项目负责人、部门主管或超级管理员可维护")
    assert_project_approved(db, task.project_id)
    if task.status == "completed":
        raise bad_request("已完成的任务不能再修改")
    before = model_to_dict(task)
    previous_parent_id = task.parent_id
    values = payload.model_dump(exclude_unset=True)
    required_fields = {
        "name",
        "owner_ids",
        "planned_start",
        "planned_end",
        "estimated_hours",
    }
    if any(values.get(key) is None for key in required_fields if key in values):
        raise bad_request("任务名称、项目成员、计划时间和预计工时不能为空")
    owner_ids = values.pop("owner_ids", None)
    normalized_owner_ids = _validate_owners(db, task.project_id, owner_ids) if owner_ids is not None else _assignee_ids(db, task.id)
    target_parent_id = values.get("parent_id", task.parent_id)
    parent = _validate_parent(db, task.project_id, target_parent_id, task.id)
    _validate_assignees_with_parent(db, parent, normalized_owner_ids)
    if target_parent_id != previous_parent_id and target_parent_id and db.scalar(
        select(ExecutionRecord.id).where(
            ExecutionRecord.task_id == target_parent_id,
            ExecutionRecord.is_deleted.is_(False),
        ).limit(1)
    ):
        raise bad_request("已有执行记录的任务不能再作为汇总任务，请先删除执行记录")
    if target_parent_id != previous_parent_id and target_parent_id and db.scalar(
        select(ScheduleBooking.id).where(
            ScheduleBooking.task_id == target_parent_id,
            ScheduleBooking.status.notin_({"rejected", "cancelled", "withdrawn"}),
        ).limit(1)
    ):
        raise bad_request("已有有效预约记录的任务不能再作为汇总任务")
    planned_start = values.get("planned_start", task.planned_start)
    planned_end = values.get("planned_end", task.planned_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    _validate_task_window(
        db,
        task.project_id,
        planned_start,
        planned_end,
        target_parent_id,
        task.id,
    )
    if {"planned_start", "planned_end"} & values.keys() and db.scalar(
        select(ScheduleBooking.id).where(
            ScheduleBooking.task_id == task.id,
            booked_schedule_predicate(),
            or_(
                ScheduleBooking.start_time < datetime.combine(planned_start, time.min),
                ScheduleBooking.end_time >= datetime.combine(
                    planned_end + timedelta(days=1), time.min
                ),
            ),
        ).limit(1)
    ):
        raise bad_request("任务计划时间不能排除已有预约时间")
    target_estimated_hours = values.get("estimated_hours", task.estimated_hours)
    if "estimated_hours" in values:
        booked_hours = _active_booking_hours(db, task.id)
        if values["estimated_hours"] < booked_hours:
            raise bad_request(
                f"当前任务已有 {booked_hours} 小时有效预约，预计工时不能小于有效预约工时"
            )
    _validate_estimated_hours(
        db,
        task.project_id,
        target_parent_id,
        target_estimated_hours,
        task.id,
    )
    previous_owner_ids = set(_assignee_ids(db, task.id))
    owner_changed = set(normalized_owner_ids) != previous_owner_ids
    if owner_changed:
        for child_id in db.scalars(
            select(Task.id).where(
                Task.parent_id == task.id,
                Task.is_deleted.is_(False),
            )
        ).all():
            if not set(_assignee_ids(db, child_id)) <= set(normalized_owner_ids):
                raise bad_request("父任务移除项目成员前，必须先从其子任务中移除该成员")
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
    if previous_parent_id != task.parent_id:
        synchronize_parent_status(db, previous_parent_id)
    if owner_changed:
        synchronize_task_status(db, task.id)
    else:
        synchronize_parent_status(db, task.parent_id)
        synchronize_project_status(db, task.project_id)
    if owner_changed:
        for owner_id in previous_owner_ids - set(normalized_owner_ids):
            create_notification(db, owner_id, "task_owner_changed", "任务项目成员已变更", f"你已不再参与任务“{task.name}”。", level="warning", related_type="task", related_id=task.id)
        for owner_id in set(normalized_owner_ids) - previous_owner_ids:
            create_notification(db, owner_id, "task_owner_changed", "任务项目成员已变更", f"你已加入任务“{task.name}”。", level="warning", related_type="task", related_id=task.id)
    if time_changed:
        for owner_id in normalized_owner_ids:
            create_notification(db, owner_id, "task_time_changed", "任务计划日期发生变化", f"任务“{task.name}”的计划日期已调整为 {task.planned_start:%Y-%m-%d} 至 {task.planned_end:%Y-%m-%d}。", level="warning", related_type="task", related_id=task.id)
    log_operation(db, operator_id=user.id, module="task", action="update", object_type="task", object_id=task.id, before_data=before, after_data=model_to_dict(task))
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int, user: User) -> None:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    assert_project_manageable(db, task.project_id, user)
    assert_project_approved(db, task.project_id)
    if task.status != "not_started":
        raise bad_request("only not-started tasks can be deleted")
    if db.scalar(
        select(Task.id)
        .where(Task.parent_id == task_id, Task.is_deleted.is_(False))
        .limit(1)
    ):
        raise conflict("delete child tasks before deleting this task", 40931)

    if db.scalar(
        select(ExecutionRecord.id).where(
            ExecutionRecord.task_id == task_id,
            ExecutionRecord.is_deleted.is_(False),
        ).limit(1)
    ):
        raise conflict(
            "delete the task's execution records before deleting it",
            40936,
            {"dependencies": ["execution records"]},
        )

    synchronize_schedule_statuses(db)
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
    parent_id = task.parent_id
    task.is_deleted = True
    db.flush()
    synchronize_parent_status(db, parent_id)
    synchronize_project_status(db, task.project_id)
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
