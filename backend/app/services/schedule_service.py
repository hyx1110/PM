from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dependencies import get_permission_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.schedule_repository import schedule_repository
from app.schemas.schedule import ScheduleCreate, ScheduleDecision, ScheduleUpdate
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_manageable, visible_project_ids
from app.utils.model import model_to_dict


def _duration_hours(start_time, end_time) -> Decimal:
    return Decimal(str(round((end_time - start_time).total_seconds() / 3600, 2)))


def _validate_relations(db: Session, user_id: int, project_id: int, task_id: int) -> None:
    if not db.get(User, user_id):
        raise not_found("scheduled user not found")
    if not db.get(Project, project_id):
        raise not_found("project not found")
    task = db.get(Task, task_id)
    if not task:
        raise not_found("task not found")
    if task.project_id != project_id:
        raise bad_request("task does not belong to project")


def _raise_conflicts(db: Session, user_id: int, start_time, end_time, exclude_id: int | None = None) -> None:
    conflicts = schedule_repository.find_conflicts(db, user_id, start_time, end_time, exclude_id)
    if conflicts:
        raise conflict("schedule conflict", 40901, {"conflicts": conflicts})


def list_schedules(db: Session, user: User, page: int, page_size: int, **filters):
    items, total = schedule_repository.list(
        db,
        page,
        page_size,
        visible_project_ids=visible_project_ids(db, user),
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def schedule_detail(db: Session, schedule_id: int, user: User) -> dict:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    scope = visible_project_ids(db, user)
    if scope is not None and item.project_id not in scope and item.user_id != user.id:
        raise forbidden("schedule is outside your data scope")
    return schedule_repository.detail(db, schedule_id)


def create_schedule(db: Session, payload: ScheduleCreate, user: User) -> ScheduleBooking:
    assert_project_manageable(db, payload.project_id, user)
    _validate_relations(db, payload.user_id, payload.project_id, payload.task_id)
    _raise_conflicts(db, payload.user_id, payload.start_time, payload.end_time)
    values = payload.model_dump()
    values["planned_hours"] = payload.planned_hours or _duration_hours(payload.start_time, payload.end_time)
    item = ScheduleBooking(**values, status="draft", created_by=user.id)
    db.add(item)
    db.flush()
    log_operation(db, operator_id=user.id, module="schedule", action="create", object_type="schedule_booking", object_id=item.id, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def update_schedule(db: Session, schedule_id: int, payload: ScheduleUpdate, user: User) -> ScheduleBooking:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected", "confirmed"}:
        raise bad_request("current schedule status does not allow editing")
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True)
    user_id = values.get("user_id", item.user_id)
    project_id = values.get("project_id", item.project_id)
    task_id = values.get("task_id", item.task_id)
    start_time = values.get("start_time", item.start_time)
    end_time = values.get("end_time", item.end_time)
    if end_time <= start_time:
        raise bad_request("end_time must be later than start_time")
    assert_project_manageable(db, project_id, user)
    _validate_relations(db, user_id, project_id, task_id)
    _raise_conflicts(db, user_id, start_time, end_time, schedule_id)
    for key, value in values.items():
        setattr(item, key, value)
    if "planned_hours" not in values or values.get("planned_hours") is None:
        item.planned_hours = _duration_hours(start_time, end_time)
    if item.status == "confirmed":
        item.status = "changed"
    item.rejection_reason = None
    db.flush()
    log_operation(db, operator_id=user.id, module="schedule", action="update", object_type="schedule_booking", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def submit_schedule(db: Session, schedule_id: int, user: User) -> ScheduleBooking:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected"}:
        raise bad_request("only draft or rejected schedules can be submitted")
    assert_project_manageable(db, item.project_id, user)
    _raise_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    before = model_to_dict(item)
    item.status = "pending"
    item.rejection_reason = None
    log_operation(db, operator_id=user.id, module="schedule", action="submit", object_type="schedule_booking", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def _assert_decision_access(db: Session, item: ScheduleBooking, user: User) -> None:
    if item.user_id == user.id:
        return
    if "schedule:edit" not in get_permission_codes(db, user.id):
        raise forbidden("only the scheduled user or an authorized manager may make this decision")
    assert_project_manageable(db, item.project_id, user)


def confirm_schedule(db: Session, schedule_id: int, payload: ScheduleDecision, user: User) -> ScheduleBooking:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(db, item, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("only pending or changed schedules can be confirmed")
    _raise_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    before = model_to_dict(item)
    item.status = "confirmed"
    item.rejection_reason = None
    log_operation(db, operator_id=user.id, module="schedule", action="confirm", object_type="schedule_booking", object_id=item.id, before_data=before, after_data=model_to_dict(item), reason=payload.reason)
    db.commit()
    db.refresh(item)
    return item


def reject_schedule(db: Session, schedule_id: int, payload: ScheduleDecision, user: User) -> ScheduleBooking:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(db, item, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("only pending or changed schedules can be rejected")
    before = model_to_dict(item)
    item.status = "rejected"
    item.rejection_reason = payload.reason
    log_operation(db, operator_id=user.id, module="schedule", action="reject", object_type="schedule_booking", object_id=item.id, before_data=before, after_data=model_to_dict(item), reason=payload.reason)
    db.commit()
    db.refresh(item)
    return item


def delete_schedule(db: Session, schedule_id: int, user: User) -> None:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "cancelled"}:
        raise bad_request("only draft or cancelled schedules can be deleted")
    assert_project_manageable(db, item.project_id, user)
    before = model_to_dict(item)
    log_operation(db, operator_id=user.id, module="schedule", action="delete", object_type="schedule_booking", object_id=item.id, before_data=before)
    db.delete(item)
    db.commit()
