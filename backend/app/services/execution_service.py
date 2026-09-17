from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.models.evaluation import TaskEvaluation
from app.models.execution import ExecutionRecord
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.execution_repository import execution_repository
from app.schemas.execution import EXECUTION_STATUSES, ExecutionCreate, ExecutionUpdate
from app.services.operation_log_service import log_operation
from app.services.status_sync_service import synchronize_task_status
from app.services.work_calendar_service import calculate_workday_hours
from app.utils.model import model_to_dict
from app.utils.time import beijing_today


def _assert_project_not_evaluated(db: Session, project_id: int) -> None:
    if db.scalar(
        select(TaskEvaluation.id)
        .join(Task, Task.id == TaskEvaluation.task_id)
        .where(
            Task.project_id == project_id,
            Task.is_deleted.is_(False),
        )
        .limit(1)
    ):
        raise bad_request("项目已进入评价阶段，不能再新增、修改或删除执行记录")


def _validate_actual_dates(start_date, end_date) -> None:
    today = beijing_today()
    if start_date > today or (end_date and end_date > today):
        raise bad_request("实际执行日期不能晚于今天")


def _resolve_actual_hours(
    db: Session,
    start_date,
    end_date,
    supplied_hours: Decimal | None,
) -> Decimal:
    _validate_actual_dates(start_date, end_date)
    capacity = calculate_workday_hours(db, start_date, end_date or start_date)
    if capacity <= 0:
        raise bad_request("所选日期范围不包含工作日")
    actual_hours = supplied_hours if supplied_hours is not None else capacity
    if actual_hours <= 0:
        raise bad_request("实际工时必须大于 0")
    if actual_hours > capacity:
        raise bad_request(f"实际工时不能超过所选工作日容量 {capacity} 小时")
    return actual_hours


def list_executions(db: Session, user: User, page: int, page_size: int, mine: bool = False, **filters):
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date and end_date and end_date < start_date:
        raise bad_request("结束日期不能早于开始日期")
    if mine:
        filters["user_id"] = user.id
    items, total = execution_repository.list(
        db,
        page,
        page_size,
        visible_project_ids=None,
        own_user_id=user.id,
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def execution_detail(db: Session, execution_id: int, user: User) -> dict:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    if record.user_id != user.id:
        raise forbidden("只能查看自己的执行记录")
    return execution_repository.detail(db, execution_id)


def create_execution(db: Session, payload: ExecutionCreate, user: User) -> ExecutionRecord:
    task = db.get(Task, payload.task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    _assert_project_not_evaluated(db, task.project_id)
    if task.status in {"completed", "cancelled"}:
        raise bad_request("已完成或已取消的任务不能新增执行记录")
    if db.scalar(
        select(Task.id).where(
            Task.parent_id == task.id,
            Task.is_deleted.is_(False),
        ).limit(1)
    ):
        raise bad_request("汇总任务不能直接填报执行记录，请在其子任务中填报")
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
    actual_hours = _resolve_actual_hours(
        db, payload.actual_start, payload.actual_end, payload.actual_hours
    )
    record = ExecutionRecord(**values, user_id=target_user_id, actual_hours=actual_hours)
    db.add(record)
    db.flush()
    synchronize_task_status(db, task.id)
    log_operation(db, operator_id=user.id, module="execution", action="create", object_type="execution_record", object_id=record.id, after_data=model_to_dict(record))
    db.commit()
    db.refresh(record)
    return record


def update_execution(db: Session, execution_id: int, payload: ExecutionUpdate, user: User) -> ExecutionRecord:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    task = db.get(Task, record.task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    _assert_project_not_evaluated(db, task.project_id)
    if record.user_id != user.id:
        raise forbidden("只能修改自己的执行记录")
    before = model_to_dict(record)
    values = payload.model_dump(exclude_unset=True)
    if "actual_start" in values and values["actual_start"] is None:
        raise bad_request("actual_start cannot be empty")
    if "status" in values and values["status"] is None:
        raise bad_request("execution status cannot be empty")
    actual_start = values.get("actual_start", record.actual_start)
    actual_end = values.get("actual_end", record.actual_end)
    status = values.get("status", record.status)
    if actual_end and actual_end < actual_start:
        raise bad_request("actual_end must be on or after actual_start")
    if status not in EXECUTION_STATUSES:
        raise bad_request("invalid execution status")
    if status == "completed" and actual_end is None:
        raise bad_request("completed execution must have actual_end")
    supplied_hours = values.pop("actual_hours", record.actual_hours)
    for key, value in values.items():
        setattr(record, key, value)
    record.actual_hours = _resolve_actual_hours(
        db, actual_start, actual_end, supplied_hours
    )
    db.flush()
    synchronize_task_status(db, task.id)
    log_operation(db, operator_id=user.id, module="execution", action="update", object_type="execution_record", object_id=record.id, before_data=before, after_data=model_to_dict(record))
    db.commit()
    db.refresh(record)
    return record


def delete_execution(db: Session, execution_id: int, user: User) -> None:
    record = execution_repository.get(db, execution_id)
    if not record:
        raise not_found("execution record not found")
    task = db.get(Task, record.task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    _assert_project_not_evaluated(db, task.project_id)
    if record.user_id != user.id:
        raise forbidden("只能删除自己的执行记录")
    before = model_to_dict(record)
    record.is_deleted = True
    db.flush()
    synchronize_task_status(db, task.id)
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
