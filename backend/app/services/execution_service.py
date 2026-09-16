from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.models.execution import ExecutionRecord
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.execution_repository import execution_repository
from app.schemas.execution import ExecutionCreate, ExecutionUpdate
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_visible
from app.utils.model import model_to_dict


def _duration_hours(start_time, end_time) -> Decimal:
    if not end_time:
        return Decimal("0")
    return Decimal(str(round((end_time - start_time).total_seconds() / 3600, 2)))


def list_executions(db: Session, user: User, page: int, page_size: int, mine: bool = False, **filters):
    if mine:
        filters["user_id"] = user.id
    items, total = execution_repository.list(
        db,
        page,
        page_size,
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
    if not task or task.is_deleted:
        raise not_found("task not found")
    assert_project_visible(db, task.project_id, user)
    target_user_id = user.id
    target_user = db.get(User, target_user_id)
    if not target_user or target_user.is_deleted or target_user.status != "active":
        raise not_found("execution user not found")
    if payload.user_id is not None and payload.user_id != user.id:
        raise forbidden("只能填写自己的执行记录")
    if not db.scalar(select(TaskAssignee.id).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == user.id)):
        raise forbidden("用户只能填报自己负责任务的执行记录")
    # user_id and actual_hours are resolved below. Excluding both prevents
    # passing actual_hours twice when constructing ExecutionRecord.
    values = payload.model_dump(exclude={"user_id", "actual_hours"})
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
    if record.user_id != user.id:
        raise forbidden("只能修改自己的执行记录")
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


def delete_execution(db: Session, execution_id: int, user: User) -> None:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    task = db.get(Task, record.task_id)
    assert_project_visible(db, task.project_id, user)
    if record.user_id != user.id:
        raise forbidden("只能删除自己的执行记录")
    before = model_to_dict(record)
    record.is_deleted = True
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="execution",
        action="delete",
        object_type="execution_record",
        object_id=execution_id,
        before_data=before,
    )
    db.commit()
