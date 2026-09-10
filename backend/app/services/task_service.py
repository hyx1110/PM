from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.models.project import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.repositories.task_repository import task_repository
from app.schemas.task import TASK_STATUSES, TASK_TYPES, TaskCreate, TaskUpdate
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_manageable, assert_project_visible, visible_project_ids
from app.utils.model import model_to_dict


def effective_status(task_status: str, planned_end: datetime, now: datetime | None = None) -> str:
    current = now or datetime.now()
    if current > planned_end and task_status not in {"completed", "cancelled"}:
        return "delayed"
    return task_status


def _validate_owner(db: Session, project_id: int, owner_id: int) -> None:
    owner = db.get(User, owner_id)
    if not owner:
        raise not_found("task owner not found")
    project = assert_project_visible(db, project_id, owner)
    if project.manager_id == owner_id:
        return
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == owner_id,
        ProjectMember.left_at.is_(None),
    ).first()
    if not member:
        raise bad_request("task owner must be an active project member")


def list_tasks(db: Session, user: User, page: int, page_size: int, project_id: int | None, owner_id: int | None, status: str | None):
    items, total = task_repository.list(db, page, page_size, project_id, owner_id, status, visible_project_ids(db, user))
    for item in items:
        item["effective_status"] = effective_status(item["status"], item["planned_end"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
    parent = db.get(Task, parent_id)
    if not parent or parent.project_id != project_id:
        raise bad_request("parent task must belong to the same project")
    cursor = parent
    while cursor:
        if current_task_id and cursor.id == current_task_id:
            raise bad_request("task hierarchy cannot contain a cycle")
        cursor = db.get(Task, cursor.parent_id) if cursor.parent_id else None


def create_task(db: Session, payload: TaskCreate, user: User) -> Task:
    assert_project_manageable(db, payload.project_id, user)
    _validate_owner(db, payload.project_id, payload.owner_id)
    _validate_parent(db, payload.project_id, payload.parent_id)
    task = Task(**payload.model_dump())
    db.add(task)
    db.flush()
    log_operation(db, operator_id=user.id, module="task", action="create", object_type="task", object_id=task.id, after_data=model_to_dict(task))
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate, user: User) -> Task:
    task = task_repository.get(db, task_id)
    if not task:
        raise not_found("task not found")
    assert_project_manageable(db, task.project_id, user)
    before = model_to_dict(task)
    values = payload.model_dump(exclude_unset=True)
    owner_id = values.get("owner_id", task.owner_id)
    _validate_owner(db, task.project_id, owner_id)
    _validate_parent(db, task.project_id, values.get("parent_id", task.parent_id), task.id)
    planned_start = values.get("planned_start", task.planned_start)
    planned_end = values.get("planned_end", task.planned_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    if values.get("task_type") and values["task_type"] not in TASK_TYPES:
        raise bad_request("invalid task type")
    if values.get("status") and values["status"] not in TASK_STATUSES:
        raise bad_request("invalid task status")
    for key, value in values.items():
        setattr(task, key, value)
    db.flush()
    log_operation(db, operator_id=user.id, module="task", action="update", object_type="task", object_id=task.id, before_data=before, after_data=model_to_dict(task))
    db.commit()
    db.refresh(task)
    return task
