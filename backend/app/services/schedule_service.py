from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException, bad_request, conflict, forbidden, not_found
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.project_repository import BOOKED_HOUR_STATUSES
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
from app.services.project_service import assert_project_booking_manager, visible_project_ids
from app.services.work_calendar_service import calculate_work_hours
from app.utils.model import model_to_dict


def _validate_relations(db: Session, user_id: int, project_id: int, task_id: int) -> None:
    scheduled_user = db.get(User, user_id)
    if not scheduled_user or scheduled_user.is_deleted or scheduled_user.status != "active":
        raise not_found("scheduled user not found")
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过 L3 审批，不能预约人力")
    task = db.get(Task, task_id)
    if not task:
        raise not_found("task not found")
    if task.project_id != project_id:
        raise bad_request("task does not belong to project")


def _raise_conflicts(
    db: Session,
    user_id: int,
    start_time,
    end_time,
    exclude_id: int | None = None,
) -> None:
    conflicts = schedule_repository.find_conflicts(
        db, user_id, start_time, end_time, exclude_id
    )
    if conflicts:
        raise conflict("schedule conflict", 40901, {"conflicts": conflicts})


def _used_project_hours(
    db: Session,
    project_id: int,
    exclude_id: int | None = None,
) -> Decimal:
    filters = [
        ScheduleBooking.project_id == project_id,
        ScheduleBooking.status.in_(BOOKED_HOUR_STATUSES),
    ]
    if exclude_id:
        filters.append(ScheduleBooking.id != exclude_id)
    return db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(*filters)
    ) or Decimal("0")


def _assert_project_capacity(
    db: Session,
    project: Project,
    requested_hours: Decimal,
    exclude_id: int | None = None,
) -> None:
    used = _used_project_hours(db, project.id, exclude_id)
    remaining = project.budget_hours - used
    if requested_hours > remaining:
        raise bad_request(
            f"项目剩余工时不足：剩余 {max(remaining, Decimal('0'))} 小时，"
            f"本次需要 {requested_hours} 小时。请先发起追加工时申请并等待 L3 审批"
        )


def _notify_assignee(db: Session, item: ScheduleBooking, title: str, content: str) -> None:
    create_notification(
        db,
        item.user_id,
        "schedule_confirmation_required",
        title,
        content,
        level="warning",
        related_type="schedule",
        related_id=item.id,
    )


def _get_schedule_for_update(db: Session, schedule_id: int) -> ScheduleBooking | None:
    return db.scalar(
        select(ScheduleBooking)
        .where(ScheduleBooking.id == schedule_id)
        .with_for_update()
    )


def list_schedules(db: Session, user: User, page: int, page_size: int, **filters):
    items, total = schedule_repository.list(
        db,
        page,
        page_size,
        visible_project_ids=visible_project_ids(db, user),
        viewer_user_id=user.id,
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_my_pending_schedules(db: Session, user: User, limit: int = 10) -> list[dict]:
    """Return only bookings that require a decision from the signed-in assignee."""
    return schedule_repository.list_pending_for_user(db, user.id, limit)


def schedule_detail(db: Session, schedule_id: int, user: User) -> dict:
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    scope = visible_project_ids(db, user)
    if (
        scope is not None
        and item.project_id not in scope
        and item.user_id != user.id
        and item.created_by != user.id
    ):
        raise forbidden("schedule is outside your data scope")
    return schedule_repository.detail(db, schedule_id)


def create_schedule(db: Session, payload: ScheduleCreate, user: User) -> ScheduleBooking:
    project = assert_project_booking_manager(db, payload.project_id, user)
    _validate_relations(db, payload.user_id, payload.project_id, payload.task_id)
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    _raise_conflicts(db, payload.user_id, payload.start_time, payload.end_time)
    _assert_project_capacity(db, project, hours)
    values = payload.model_dump(exclude={"planned_hours"})
    item = ScheduleBooking(
        **values,
        planned_hours=hours,
        status="pending",
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    _notify_assignee(
        db,
        item,
        "收到新的人力预约",
        f"项目经理预约了你 {item.start_time:%Y-%m-%d %H:%M} 至 "
        f"{item.end_time:%H:%M} 的 {item.planned_hours} 小时，请由你本人确认。",
    )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="submit",
        object_type="schedule_booking",
        object_id=item.id,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def update_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleUpdate,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"pending", "rejected", "confirmed"}:
        raise bad_request("current schedule status does not allow editing")
    if item.created_by != user.id:
        raise forbidden("只有该预约的提交人可以修改")
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True, exclude={"planned_hours"})
    user_id = values.get("user_id", item.user_id)
    project_id = values.get("project_id", item.project_id)
    task_id = values.get("task_id", item.task_id)
    start_time = values.get("start_time", item.start_time)
    end_time = values.get("end_time", item.end_time)
    project = assert_project_booking_manager(db, project_id, user)
    _validate_relations(db, user_id, project_id, task_id)
    hours = calculate_work_hours(db, start_time, end_time)
    _raise_conflicts(db, user_id, start_time, end_time, schedule_id)
    _assert_project_capacity(
        db,
        project,
        hours,
        schedule_id if project_id == item.project_id else None,
    )
    for key, value in values.items():
        setattr(item, key, value)
    item.planned_hours = hours
    item.status = "changed" if item.status == "confirmed" else "pending"
    item.version += 1
    item.rejection_reason = None
    db.flush()
    _notify_assignee(
        db,
        item,
        "人力预约待重新确认",
        f"预约 #{item.id} 已变更为 {item.start_time:%Y-%m-%d %H:%M} 至 "
        f"{item.end_time:%H:%M}，请由你本人确认。",
    )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="update",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def submit_schedule(db: Session, schedule_id: int, user: User) -> ScheduleBooking:
    """Submit legacy draft rows created before v2.0; new bookings are submitted directly."""
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected"}:
        raise bad_request("only legacy draft or rejected schedules can be submitted")
    if item.created_by != user.id:
        raise forbidden("只有该预约的提交人可以提交")
    project = assert_project_booking_manager(db, item.project_id, user)
    hours = calculate_work_hours(db, item.start_time, item.end_time)
    _raise_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    _assert_project_capacity(db, project, hours, item.id)
    before = model_to_dict(item)
    item.planned_hours = hours
    item.status = "pending"
    item.version += 1
    item.rejection_reason = None
    _notify_assignee(
        db,
        item,
        "人力预约待确认",
        f"预约 #{item.id} 已提交，请由你本人确认。",
    )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="submit",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def _assert_decision_access(item: ScheduleBooking, user: User) -> None:
    if item.user_id != user.id:
        raise forbidden("只有被预约人本人可以确认或拒绝该人力预约")


def confirm_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleDecision,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(item, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("only pending or changed schedules can be confirmed")
    calculate_work_hours(db, item.start_time, item.end_time)
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
            "人力预约已确认",
            f"预约 #{item.id} 已由被预约人本人确认。",
            related_type="schedule",
            related_id=item.id,
        )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="confirm",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
        reason=payload.reason,
    )
    db.commit()
    db.refresh(item)
    return item


def reject_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleDecision,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(item, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("only pending or changed schedules can be rejected")
    if not payload.reason:
        raise bad_request("拒绝预约时必须填写原因")
    before = model_to_dict(item)
    item.status = "rejected"
    item.version += 1
    item.rejection_reason = payload.reason
    if item.created_by != user.id:
        create_notification(
            db,
            item.created_by,
            "schedule_rejected",
            "人力预约被拒绝",
            f"预约 #{item.id} 被预约人拒绝：{payload.reason}",
            level="warning",
            related_type="schedule",
            related_id=item.id,
        )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="reject",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
        reason=payload.reason,
    )
    db.commit()
    db.refresh(item)
    return item


def withdraw_schedule(db: Session, schedule_id: int, user: User) -> ScheduleBooking:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.created_by != user.id:
        raise forbidden("只有该预约的提交人可以撤回")
    assert_project_booking_manager(db, item.project_id, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("只有对方尚未确认的预约可以撤回")
    before = model_to_dict(item)
    item.status = "withdrawn"
    item.version += 1
    create_notification(
        db,
        item.user_id,
        "schedule_withdrawn",
        "人力预约已撤回",
        f"预约 #{item.id} 已由项目经理撤回，无需再审批。",
        related_type="schedule",
        related_id=item.id,
    )
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="withdraw",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def delete_schedule(db: Session, schedule_id: int, user: User) -> None:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected", "cancelled", "withdrawn"}:
        raise bad_request("only draft, rejected, cancelled or withdrawn schedules can be deleted")
    if item.created_by != user.id:
        raise forbidden("只有该预约的提交人可以删除")
    assert_project_booking_manager(db, item.project_id, user)
    before = model_to_dict(item)
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="delete",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
    )
    db.delete(item)
    db.commit()


def move_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleMove,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.created_by != user.id:
        raise forbidden("只有该预约的提交人可以调整")
    if item.version != payload.expected_version:
        raise conflict(
            "schedule has been changed by another user",
            40903,
            {"current_version": item.version},
        )
    if item.status not in {"pending", "rejected", "confirmed"}:
        raise bad_request("current schedule status does not allow moving")
    project = assert_project_booking_manager(db, item.project_id, user)
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    _raise_conflicts(db, item.user_id, payload.start_time, payload.end_time, item.id)
    _assert_project_capacity(db, project, hours, item.id)
    before = model_to_dict(item)
    item.start_time = payload.start_time
    item.end_time = payload.end_time
    item.planned_hours = hours
    item.version += 1
    item.status = "changed" if item.status == "confirmed" else "pending"
    item.rejection_reason = None
    _notify_assignee(
        db,
        item,
        "人力预约时间已调整",
        f"预约 #{item.id} 已移动到 {item.start_time:%Y-%m-%d %H:%M} 至 "
        f"{item.end_time:%H:%M}，请由你本人确认。",
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


def batch_create_schedules(
    db: Session,
    payload: ScheduleBatchCreate,
    user: User,
) -> dict:
    project = assert_project_booking_manager(db, payload.project_id, user)
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    for user_id in payload.user_ids:
        _validate_relations(db, user_id, payload.project_id, payload.task_id)
    all_conflicts = []
    for user_id in payload.user_ids:
        all_conflicts.extend(
            schedule_repository.find_conflicts(
                db, user_id, payload.start_time, payload.end_time
            )
        )
    if all_conflicts:
        raise conflict("schedule conflict", 40901, {"conflicts": all_conflicts})
    _assert_project_capacity(db, project, hours * len(payload.user_ids))
    items = []
    for user_id in payload.user_ids:
        item = ScheduleBooking(
            user_id=user_id,
            project_id=payload.project_id,
            task_id=payload.task_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            planned_hours=hours,
            remark=payload.remark,
            status="pending",
            created_by=user.id,
        )
        db.add(item)
        db.flush()
        _notify_assignee(
            db,
            item,
            "收到新的人力预约",
            f"项目经理预约了你 {item.start_time:%Y-%m-%d %H:%M} 至 "
            f"{item.end_time:%H:%M} 的 {item.planned_hours} 小时，请由你本人确认。",
        )
        log_operation(
            db,
            operator_id=user.id,
            module="schedule",
            action="batch_submit",
            object_type="schedule_booking",
            object_id=item.id,
            after_data=model_to_dict(item),
        )
        items.append(item)
    db.commit()
    return {"created": len(items), "schedule_ids": [item.id for item in items]}


def copy_week(db: Session, payload: ScheduleCopyWeek, user: User) -> dict:
    from datetime import timedelta

    source_start = payload.source_week_start
    source_end = source_start + timedelta(days=7)
    delta = payload.target_week_start - source_start
    filters = [
        ScheduleBooking.start_time >= source_start,
        ScheduleBooking.start_time < source_end,
        ScheduleBooking.status.in_(payload.include_statuses),
        ScheduleBooking.created_by == user.id,
    ]
    if payload.user_ids:
        filters.append(ScheduleBooking.user_id.in_(payload.user_ids))
    source_items = db.scalars(
        select(ScheduleBooking).where(*filters).order_by(ScheduleBooking.start_time)
    ).all()
    created_ids: list[int] = []
    skipped: list[dict] = []
    checked_projects: dict[int, Project] = {}
    for source in source_items:
        if source.project_id not in checked_projects:
            checked_projects[source.project_id] = assert_project_booking_manager(
                db, source.project_id, user
            )
        project = checked_projects[source.project_id]
        start_time = source.start_time + delta
        end_time = source.end_time + delta
        try:
            hours = calculate_work_hours(db, start_time, end_time)
            _assert_project_capacity(db, project, hours)
        except BusinessException as exc:
            skipped.append(
                {"source_schedule_id": source.id, "reason": exc.message}
            )
            continue
        conflicts = schedule_repository.find_conflicts(
            db, source.user_id, start_time, end_time
        )
        if conflicts:
            skipped.append(
                {
                    "source_schedule_id": source.id,
                    "reason": "conflict",
                    "conflicts": conflicts,
                }
            )
            continue
        item = ScheduleBooking(
            user_id=source.user_id,
            project_id=source.project_id,
            task_id=source.task_id,
            start_time=start_time,
            end_time=end_time,
            planned_hours=hours,
            remark=source.remark,
            status="pending",
            created_by=user.id,
            source_booking_id=source.id,
        )
        db.add(item)
        db.flush()
        _notify_assignee(
            db,
            item,
            "收到复制的人力预约",
            f"项目经理预约了你 {item.start_time:%Y-%m-%d %H:%M} 至 "
            f"{item.end_time:%H:%M}，请由你本人确认。",
        )
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
    return {
        "source_count": len(source_items),
        "created": len(created_ids),
        "schedule_ids": created_ids,
        "skipped": skipped,
    }
