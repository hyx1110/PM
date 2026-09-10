from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.execution import ExecutionRecord
from app.models.task import Task
from app.models.user import User
from app.repositories.execution_repository import execution_repository
from app.schemas.execution import ExecutionCreate, ExecutionUpdate
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_visible, visible_project_ids
from app.utils.model import model_to_dict


def _duration_hours(start_time, end_time) -> Decimal:
    if not end_time:
        return Decimal("0")
    return Decimal(str(round((end_time - start_time).total_seconds() / 3600, 2)))


def _can_edit_other_users(db: Session, user: User) -> bool:
    return bool(get_role_codes(db, user.id) & {"super_admin", "department_manager", "functional_manager", "project_manager"})


def list_executions(db: Session, user: User, page: int, page_size: int, mine: bool = False, **filters):
    if mine:
        filters["user_id"] = user.id
    items, total = execution_repository.list(
        db,
        page,
        page_size,
        visible_project_ids=visible_project_ids(db, user),
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def execution_detail(db: Session, execution_id: int, user: User) -> dict:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    task = db.get(Task, record.task_id)
    assert_project_visible(db, task.project_id, user)
    return execution_repository.detail(db, execution_id)


def create_execution(db: Session, payload: ExecutionCreate, user: User) -> ExecutionRecord:
    task = db.get(Task, payload.task_id)
    if not task:
        raise not_found("task not found")
    assert_project_visible(db, task.project_id, user)
    target_user_id = payload.user_id or user.id
    if not db.get(User, target_user_id):
        raise not_found("execution user not found")
    if target_user_id != user.id and not _can_edit_other_users(db, user):
        raise forbidden("users may only create their own execution records")
    values = payload.model_dump(exclude={"user_id"})
    actual_hours = payload.actual_hours
    if actual_hours is None:
        actual_hours = _duration_hours(payload.actual_start, payload.actual_end)
    record = ExecutionRecord(**values, user_id=target_user_id, actual_hours=actual_hours)
    db.add(record)
    db.flush()
    log_operation(db, operator_id=user.id, module="execution", action="create", object_type="execution_record", object_id=record.id, after_data=model_to_dict(record))
    db.commit()
    db.refresh(record)
    return record


def update_execution(db: Session, execution_id: int, payload: ExecutionUpdate, user: User) -> ExecutionRecord:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    task = db.get(Task, record.task_id)
    assert_project_visible(db, task.project_id, user)
    if record.user_id != user.id and not _can_edit_other_users(db, user):
        raise forbidden("users may only update their own execution records")
    before = model_to_dict(record)
    values = payload.model_dump(exclude_unset=True)
    actual_start = values.get("actual_start", record.actual_start)
    actual_end = values.get("actual_end", record.actual_end)
    if actual_end and actual_end < actual_start:
        raise bad_request("actual_end must be on or after actual_start")
    for key, value in values.items():
        setattr(record, key, value)
    if "actual_hours" not in values or values.get("actual_hours") is None:
        record.actual_hours = _duration_hours(actual_start, actual_end)
    db.flush()
    log_operation(db, operator_id=user.id, module="execution", action="update", object_type="execution_record", object_id=record.id, before_data=before, after_data=model_to_dict(record))
    db.commit()
    db.refresh(record)
    return record
