from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dependencies import get_permission_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.schedule_repository import schedule_repository
from app.schemas.schedule import (
    ScheduleBatchCreate,
    ScheduleCopyWeek,
    ScheduleCreate,
    ScheduleDecision,
    ScheduleMove,
    ScheduleUpdate,
)
from app.services.notification_service import create_notification
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
    if item.user_id != user.id:
        create_notification(
            db,
            item.user_id,
            "schedule_created",
            "收到新的排期草稿",
            f"你收到一条 {item.start_time:%Y-%m-%d %H:%M} 开始的排期，请查看并确认。",
            related_type="schedule",
            related_id=item.id,
        )
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
    item.version += 1
    item.rejection_reason = None
    db.flush()
    create_notification(
        db,
        item.user_id,
        "schedule_changed",
        "排期已变更",
        f"预约 #{item.id} 的时间或任务信息已变更，请重新查看。",
        level="warning",
        related_type="schedule",
        related_id=item.id,
    )
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
    item.version += 1
    item.rejection_reason = None
    create_notification(
        db,
        item.user_id,
        "schedule_confirmation_required",
        "排期待确认",
        f"预约 #{item.id} 已提交，请确认是否接受该安排。",
        level="warning",
        related_type="schedule",
        related_id=item.id,
    )
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
    item.version += 1
    item.rejection_reason = None
    if item.created_by != user.id:
        create_notification(
            db,
            item.created_by,
            "schedule_confirmed",
            "排期已确认",
            f"预约 #{item.id} 已由成员确认。",
            related_type="schedule",
            related_id=item.id,
        )
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
    item.version += 1
    item.rejection_reason = payload.reason
    if item.created_by != user.id:
        create_notification(
            db,
            item.created_by,
            "schedule_rejected",
            "排期被拒绝",
            f"预约 #{item.id} 被拒绝：{payload.reason or '未填写原因'}",
            level="warning",
            related_type="schedule",
            related_id=item.id,
        )
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


def move_schedule(db: Session, schedule_id: int, payload: ScheduleMove, user: User) -> ScheduleBooking:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.version != payload.expected_version:
        raise conflict(
            "schedule has been changed by another user",
            40903,
            {"current_version": item.version},
        )
    if item.status not in {"draft", "rejected", "confirmed"}:
        raise bad_request("current schedule status does not allow moving")
    assert_project_manageable(db, item.project_id, user)
    _raise_conflicts(db, item.user_id, payload.start_time, payload.end_time, item.id)
    before = model_to_dict(item)
    item.start_time = payload.start_time
    item.end_time = payload.end_time
    item.planned_hours = _duration_hours(payload.start_time, payload.end_time)
    item.version += 1
    if item.status == "confirmed":
        item.status = "changed"
    item.rejection_reason = None
    create_notification(
        db,
        item.user_id,
        "schedule_changed",
        "排期已拖动调整",
        f"预约 #{item.id} 已移动到 {item.start_time:%Y-%m-%d %H:%M}。",
        level="warning",
        related_type="schedule",
        related_id=item.id,
    )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="move",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def batch_create_schedules(db: Session, payload: ScheduleBatchCreate, user: User) -> dict:
    assert_project_manageable(db, payload.project_id, user)
    for user_id in payload.user_ids:
        _validate_relations(db, user_id, payload.project_id, payload.task_id)
    all_conflicts = []
    for user_id in payload.user_ids:
        all_conflicts.extend(
            schedule_repository.find_conflicts(db, user_id, payload.start_time, payload.end_time)
        )
    if all_conflicts:
        raise conflict("schedule conflict", 40901, {"conflicts": all_conflicts})
    items = []
    for user_id in payload.user_ids:
        item = ScheduleBooking(
            user_id=user_id,
            project_id=payload.project_id,
            task_id=payload.task_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            planned_hours=payload.planned_hours or _duration_hours(payload.start_time, payload.end_time),
            remark=payload.remark,
            status="draft",
            created_by=user.id,
        )
        db.add(item)
        db.flush()
        if user_id != user.id:
            create_notification(
                db,
                user_id,
                "schedule_created",
                "收到新的批量排期",
                f"你收到一条 {item.start_time:%Y-%m-%d %H:%M} 开始的排期草稿。",
                related_type="schedule",
                related_id=item.id,
            )
        log_operation(
            db,
            operator_id=user.id,
            module="schedule",
            action="batch_create",
            object_type="schedule_booking",
            object_id=item.id,
            after_data=model_to_dict(item),
        )
        items.append(item)
    db.commit()
    return {"created": len(items), "schedule_ids": [item.id for item in items]}


def copy_week(db: Session, payload: ScheduleCopyWeek, user: User) -> dict:
    from datetime import timedelta
    from sqlalchemy import select

    source_start = payload.source_week_start
    source_end = source_start + timedelta(days=7)
    delta = payload.target_week_start - source_start
    filters = [
        ScheduleBooking.start_time >= source_start,
        ScheduleBooking.start_time < source_end,
        ScheduleBooking.status.in_(payload.include_statuses),
    ]
    if payload.user_ids:
        filters.append(ScheduleBooking.user_id.in_(payload.user_ids))
    scope = visible_project_ids(db, user)
    if scope is not None:
        filters.append(ScheduleBooking.project_id.in_(scope or {-1}))
    source_items = db.scalars(
        select(ScheduleBooking).where(*filters).order_by(ScheduleBooking.start_time)
    ).all()
    created_ids: list[int] = []
    skipped: list[dict] = []
    checked_projects: set[int] = set()
    for source in source_items:
        if source.project_id not in checked_projects:
            assert_project_manageable(db, source.project_id, user)
            checked_projects.add(source.project_id)
        start_time = source.start_time + delta
        end_time = source.end_time + delta
        conflicts = schedule_repository.find_conflicts(db, source.user_id, start_time, end_time)
        if conflicts:
            skipped.append({"source_schedule_id": source.id, "reason": "conflict", "conflicts": conflicts})
            continue
        item = ScheduleBooking(
            user_id=source.user_id,
            project_id=source.project_id,
            task_id=source.task_id,
            start_time=start_time,
            end_time=end_time,
            planned_hours=source.planned_hours,
            remark=source.remark,
            status="draft",
            created_by=user.id,
            source_booking_id=source.id,
        )
        db.add(item)
        db.flush()
        created_ids.append(item.id)
        log_operation(
            db,
            operator_id=user.id,
            module="schedule",
            action="copy_week",
            object_type="schedule_booking",
            object_id=item.id,
            after_data=model_to_dict(item),
        )
    db.commit()
    return {"source_count": len(source_items), "created": len(created_ids), "schedule_ids": created_ids, "skipped": skipped}
