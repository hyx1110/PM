from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.project import Project, ProjectMember
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.personal_time_repository import personal_time_repository
from app.repositories.project_repository import booked_schedule_predicate
from app.repositories.schedule_repository import schedule_repository
from app.schemas.schedule import (
    ScheduleBatchCreate,
    ScheduleCreate,
    ScheduleDecision,
    ScheduleMove,
    ScheduleUpdate,
)
from app.services.notification_service import create_notification
from app.services.operation_log_service import log_operation
from app.services.project_service import assert_project_booking_access
from app.services.schedule_lifecycle_service import synchronize_schedule_statuses
from app.services.work_calendar_service import calculate_work_hours
from app.utils.model import model_to_dict
from app.services.visibility_service import visible_schedule_user_ids
from app.utils.time import beijing_now


def _can_manage_all_schedules(db: Session, user: User) -> bool:
    return bool(get_role_codes(db, user.id) & {"super_admin", "department_manager"})


def _submission_status(project: Project, target_user_id: int, actor: User, previous_status: str | None = None) -> str:
    """A user booking their own assigned task never approves themselves twice."""
    if target_user_id == actor.id:
        return "confirmed"
    return "changed" if previous_status in {"confirmed", "changed"} else "pending"


def _validate_future_schedule(start_time: datetime) -> None:
    """Reject elapsed slots before a booking can be created and auto-cancelled."""
    if start_time <= beijing_now():
        raise bad_request("不能预约已经开始或已经过去的时间段，请选择当前北京时间之后的时间")


def _validate_relations(
    db: Session,
    user_id: int,
    project_id: int,
    task_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> None:
    scheduled_user = db.get(User, user_id)
    if not scheduled_user or scheduled_user.is_deleted or scheduled_user.status != "active":
        raise not_found("scheduled user not found")
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    if project.approval_status != "approved":
        raise bad_request("项目尚未通过审批，不能预约人力")
    if project.status in {"Completed", "Cancelled"}:
        raise bad_request("已完成或已取消的项目不能预约人力")
    task = db.get(Task, task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    if task.project_id != project_id:
        raise bad_request("task does not belong to project")
    if task.status == "completed":
        raise bad_request("已完成的任务不能继续预约人力")
    if db.scalar(
        select(Task.id).where(
            Task.parent_id == task.id,
            Task.is_deleted.is_(False),
        ).limit(1)
    ):
        raise bad_request("汇总任务不能直接预约人力，请选择其子任务")
    if start_time is not None and end_time is not None:
        project_start = datetime.combine(project.planned_start, time.min)
        project_end = datetime.combine(
            project.planned_end + timedelta(days=1),
            time.min,
        )
        if start_time < project_start or end_time > project_end:
            raise bad_request("预约时间必须位于项目计划日期范围内")
        task_start = datetime.combine(task.planned_start, time.min)
        task_end = datetime.combine(task.planned_end + timedelta(days=1), time.min)
        if start_time < task_start or end_time > task_end:
            raise bad_request("预约时间必须位于任务计划日期范围内")
    if not db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.left_at.is_(None),
        )
    ):
        raise bad_request("被预约人必须是当前有效项目成员")
    if not db.scalar(
        select(TaskAssignee.id).where(
            TaskAssignee.task_id == task_id,
            TaskAssignee.user_id == user_id,
        )
    ):
        raise bad_request("只能为该任务已指定的项目成员预约时间")


def _lock_users(db: Session, user_ids: list[int]) -> None:
    ids = sorted(set(user_ids))
    if ids:
        db.scalars(
            select(User)
            .where(User.id.in_(ids))
            .order_by(User.id)
            .with_for_update()
        ).all()


def _collect_conflicts(
    db: Session,
    user_id: int,
    start_time,
    end_time,
    exclude_id: int | None = None,
) -> list[dict]:
    conflicts = schedule_repository.find_conflicts(
        db, user_id, start_time, end_time, exclude_id
    )
    conflicts.extend(
        personal_time_repository.find_conflicts(db, user_id, start_time, end_time)
    )
    return conflicts


def _raise_conflicts(
    db: Session,
    user_id: int,
    start_time,
    end_time,
    exclude_id: int | None = None,
) -> None:
    conflicts = _collect_conflicts(
        db, user_id, start_time, end_time, exclude_id
    )
    if conflicts:
        raise conflict(
            "该人员在所选时间段已有项目预约或个人安排",
            40901,
            {"conflicts": conflicts},
        )


def _used_project_hours(
    db: Session,
    project_id: int,
    exclude_id: int | None = None,
) -> Decimal:
    filters = [
        ScheduleBooking.project_id == project_id,
        booked_schedule_predicate(),
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
            f"本次需要 {requested_hours} 小时。请先发起项目资源申请并等待部门主管审批"
        )


def _assert_task_capacity(
    db: Session,
    task_id: int,
    requested_hours: Decimal,
    exclude_id: int | None = None,
) -> None:
    task = db.get(Task, task_id)
    if not task or task.is_deleted:
        raise not_found("task not found")
    filters = [
        ScheduleBooking.task_id == task_id,
        booked_schedule_predicate(),
    ]
    if exclude_id:
        filters.append(ScheduleBooking.id != exclude_id)
    used = db.scalar(
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0)).where(*filters)
    ) or Decimal("0")
    remaining = task.estimated_hours - used
    if requested_hours > remaining:
        raise bad_request(
            f"任务剩余预计工时不足：剩余 {max(remaining, Decimal('0'))} 小时，"
            f"本次需要 {requested_hours} 小时。请先调整任务预计工时"
        )


def _notify_assignee(db: Session, item: ScheduleBooking, title: str, content: str) -> None:
    if item.status not in {"pending", "changed"}:
        return
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


def _get_schedule_for_ordered_update(
    db: Session,
    schedule_id: int,
) -> ScheduleBooking | None:
    """Use project -> user -> booking locks for every schedule mutation."""
    preview = schedule_repository.get(db, schedule_id)
    if not preview:
        return None
    db.scalar(
        select(Project)
        .where(Project.id == preview.project_id)
        .with_for_update()
    )
    _lock_users(db, [preview.user_id])
    return _get_schedule_for_update(db, schedule_id)


def _reject_competing_proposals(
    db: Session,
    accepted: ScheduleBooking,
    actor_id: int,
) -> None:
    competing_items = list(
        db.scalars(
            select(ScheduleBooking)
            .where(
                ScheduleBooking.user_id == accepted.user_id,
                ScheduleBooking.id != accepted.id,
                ScheduleBooking.status.in_({"pending", "changed"}),
                ScheduleBooking.start_time < accepted.end_time,
                ScheduleBooking.end_time > accepted.start_time,
            )
            .with_for_update()
        ).all()
    )
    for competing in competing_items:
        competing.status = "rejected"
        competing.version += 1
        competing.rejection_reason = "该时间段的其他预约已由被预约人确认"
        if competing.created_by != actor_id:
            create_notification(
                db,
                competing.created_by,
                "schedule_rejected_due_to_conflict",
                "人力预约未被选中",
                f"预约 #{competing.id} 因同一时间段的其他预约已确认而自动关闭。",
                level="warning",
                related_type="schedule",
                related_id=competing.id,
            )


def list_schedules(db: Session, user: User, page: int, page_size: int, **filters):
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date and end_date and end_date < start_date:
        raise bad_request("结束日期不能早于开始日期")
    changes = synchronize_schedule_statuses(db)
    if any(changes.values()):
        db.commit()
    items, total = schedule_repository.list(
        db,
        page,
        page_size,
        # Schedule visibility is person-based: once a person is in the
        # viewer's scope, all of that person's project bookings are needed to
        # judge real availability, even when they belong to another project.
        visible_project_ids=None,
        visible_user_ids=visible_schedule_user_ids(db, user),
        viewer_user_id=user.id,
        **filters,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_my_pending_schedules(db: Session, user: User, limit: int = 10) -> list[dict]:
    """Return only bookings that require a decision from the signed-in assignee."""
    changes = synchronize_schedule_statuses(db)
    if any(changes.values()):
        db.commit()
    return schedule_repository.list_pending_for_user(db, user.id, limit)


def schedule_detail(db: Session, schedule_id: int, user: User) -> dict:
    changes = synchronize_schedule_statuses(db)
    if any(changes.values()):
        db.commit()
    item = schedule_repository.get(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    visible_user_ids = visible_schedule_user_ids(db, user)
    if (
        visible_user_ids is not None
        and item.user_id not in visible_user_ids
        and item.created_by != user.id
    ):
        raise forbidden("schedule is outside your data scope")
    if (
        item.status not in {"confirmed", "running", "completed"}
        and item.user_id != user.id
        and item.created_by != user.id
    ):
        raise forbidden("待确认或未成功的预约仅对申请人和被预约人可见")
    return schedule_repository.detail(db, schedule_id)


def create_schedule(db: Session, payload: ScheduleCreate, user: User) -> ScheduleBooking:
    _validate_future_schedule(payload.start_time)
    project = assert_project_booking_access(
        db, payload.project_id, user, [payload.user_id]
    )
    _validate_relations(
        db,
        payload.user_id,
        payload.project_id,
        payload.task_id,
        payload.start_time,
        payload.end_time,
    )
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    _lock_users(db, [payload.user_id])
    _raise_conflicts(db, payload.user_id, payload.start_time, payload.end_time)
    _assert_project_capacity(db, project, hours)
    _assert_task_capacity(db, payload.task_id, hours)
    values = payload.model_dump(exclude={"planned_hours"})
    item = ScheduleBooking(
        **values,
        planned_hours=hours,
        status=_submission_status(project, payload.user_id, user),
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    if item.status == "confirmed":
        _reject_competing_proposals(db, item, user.id)
    _notify_assignee(
        db,
        item,
        "收到新的人力预约",
        f"你收到 {item.start_time:%Y-%m-%d %H:%M} 至 "
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
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"pending", "changed", "rejected", "confirmed"}:
        raise bad_request("current schedule status does not allow editing")
    if item.created_by != user.id and not _can_manage_all_schedules(db, user):
        raise forbidden("只有该预约的提交人可以修改")
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True, exclude={"planned_hours"})
    required_fields = {"user_id", "project_id", "task_id", "start_time", "end_time"}
    if any(values.get(key) is None for key in required_fields if key in values):
        raise bad_request("预约人员、项目、任务和起止时间不能为空")
    user_id = values.get("user_id", item.user_id)
    project_id = values.get("project_id", item.project_id)
    task_id = values.get("task_id", item.task_id)
    start_time = values.get("start_time", item.start_time)
    end_time = values.get("end_time", item.end_time)
    _validate_future_schedule(start_time)
    project = assert_project_booking_access(db, project_id, user, [user_id])
    _validate_relations(
        db,
        user_id,
        project_id,
        task_id,
        start_time,
        end_time,
    )
    hours = calculate_work_hours(db, start_time, end_time)
    _lock_users(db, [user_id])
    _raise_conflicts(db, user_id, start_time, end_time, schedule_id)
    _assert_project_capacity(
        db,
        project,
        hours,
        schedule_id if project_id == item.project_id else None,
    )
    _assert_task_capacity(
        db,
        task_id,
        hours,
        schedule_id if task_id == item.task_id else None,
    )
    for key, value in values.items():
        setattr(item, key, value)
    item.planned_hours = hours
    item.status = _submission_status(project, user_id, user, item.status)
    item.version += 1
    item.rejection_reason = None
    db.flush()
    if item.status == "confirmed":
        _reject_competing_proposals(db, item, user.id)
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
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected"}:
        raise bad_request("only legacy draft or rejected schedules can be submitted")
    if item.created_by != user.id and not _can_manage_all_schedules(db, user):
        raise forbidden("只有该预约的提交人可以提交")
    _validate_future_schedule(item.start_time)
    project = assert_project_booking_access(
        db, item.project_id, user, [item.user_id]
    )
    _validate_relations(
        db,
        item.user_id,
        item.project_id,
        item.task_id,
        item.start_time,
        item.end_time,
    )
    hours = calculate_work_hours(db, item.start_time, item.end_time)
    _lock_users(db, [item.user_id])
    _raise_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    _assert_project_capacity(db, project, hours, item.id)
    _assert_task_capacity(db, item.task_id, hours, item.id)
    before = model_to_dict(item)
    item.planned_hours = hours
    item.status = _submission_status(project, item.user_id, user)
    item.version += 1
    item.rejection_reason = None
    db.flush()
    if item.status == "confirmed":
        _reject_competing_proposals(db, item, user.id)
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


def _assert_decision_access(db: Session, item: ScheduleBooking, user: User) -> None:
    if item.user_id != user.id and "super_admin" not in get_role_codes(db, user.id):
        raise forbidden("只有被预约人本人或超级管理员可以确认或拒绝该人力预约")


def confirm_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleDecision,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(db, item, user)
    if item.status not in {"pending", "changed"}:
        raise bad_request("only pending or changed schedules can be confirmed")
    _validate_relations(
        db,
        item.user_id,
        item.project_id,
        item.task_id,
        item.start_time,
        item.end_time,
    )
    calculate_work_hours(db, item.start_time, item.end_time)
    _raise_conflicts(db, item.user_id, item.start_time, item.end_time, item.id)
    project = db.get(Project, item.project_id)
    if not project or project.is_deleted:
        raise not_found("project not found")
    _assert_project_capacity(db, project, item.planned_hours, item.id)
    _assert_task_capacity(db, item.task_id, item.planned_hours, item.id)
    before = model_to_dict(item)
    item.status = "confirmed"
    item.version += 1
    item.rejection_reason = None
    _reject_competing_proposals(db, item, user.id)
    if item.created_by != user.id:
        create_notification(
            db,
            item.created_by,
            "schedule_confirmed",
            "人力预约已确认",
            f"预约 #{item.id} 已由{'被预约人本人' if item.user_id == user.id else '超级管理员'}确认。",
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
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    _assert_decision_access(db, item, user)
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
            f"预约 #{item.id} 已由{'被预约人本人' if item.user_id == user.id else '超级管理员'}拒绝：{payload.reason}",
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
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.created_by != user.id and not _can_manage_all_schedules(db, user):
        raise forbidden("只有该预约的提交人可以撤回")
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
        f"预约 #{item.id} 已由提交人撤回，无需再审批。",
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
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.status not in {"draft", "rejected", "cancelled", "withdrawn"}:
        raise bad_request("only draft, rejected, cancelled or withdrawn schedules can be deleted")
    if item.created_by != user.id and not _can_manage_all_schedules(db, user):
        raise forbidden("只有该预约的提交人可以删除")
    before = model_to_dict(item)
    item.status = "cancelled"
    item.version += 1
    log_operation(
        db,
        operator_id=user.id,
        module="schedule",
        action="cancel",
        object_type="schedule_booking",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()


def move_schedule(
    db: Session,
    schedule_id: int,
    payload: ScheduleMove,
    user: User,
) -> ScheduleBooking:
    item = _get_schedule_for_ordered_update(db, schedule_id)
    if not item:
        raise not_found("schedule not found")
    if item.created_by != user.id and not _can_manage_all_schedules(db, user):
        raise forbidden("只有该预约的提交人可以调整")
    if item.version != payload.expected_version:
        raise conflict(
            "预约已被其他操作更新，请刷新共享看板后重新拖动",
            40903,
            {"current_version": item.version},
        )
    if item.status not in {"pending", "changed", "rejected", "confirmed"}:
        raise bad_request("当前预约状态不允许拖动改期")
    _validate_future_schedule(payload.start_time)
    project = assert_project_booking_access(
        db, item.project_id, user, [item.user_id]
    )
    _validate_relations(
        db,
        item.user_id,
        item.project_id,
        item.task_id,
        payload.start_time,
        payload.end_time,
    )
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    _lock_users(db, [item.user_id])
    _raise_conflicts(db, item.user_id, payload.start_time, payload.end_time, item.id)
    _assert_project_capacity(db, project, hours, item.id)
    _assert_task_capacity(db, item.task_id, hours, item.id)
    before = model_to_dict(item)
    item.start_time = payload.start_time
    item.end_time = payload.end_time
    item.planned_hours = hours
    item.version += 1
    item.status = _submission_status(project, item.user_id, user, item.status)
    item.rejection_reason = None
    db.flush()
    if item.status == "confirmed":
        _reject_competing_proposals(db, item, user.id)
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
    _validate_future_schedule(payload.start_time)
    project = assert_project_booking_access(
        db, payload.project_id, user, payload.user_ids
    )
    hours = calculate_work_hours(db, payload.start_time, payload.end_time)
    for user_id in payload.user_ids:
        _validate_relations(
            db,
            user_id,
            payload.project_id,
            payload.task_id,
            payload.start_time,
            payload.end_time,
        )
    _lock_users(db, payload.user_ids)
    all_conflicts = []
    for user_id in payload.user_ids:
        all_conflicts.extend(
            _collect_conflicts(
                db, user_id, payload.start_time, payload.end_time
            )
        )
    if all_conflicts:
        raise conflict("schedule conflict", 40901, {"conflicts": all_conflicts})
    # Pending proposals do not reserve capacity. Each proposal must be
    # individually feasible; confirmation performs the serialized final check.
    _assert_project_capacity(db, project, hours)
    _assert_task_capacity(db, payload.task_id, hours)
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
            status=_submission_status(project, user_id, user),
            created_by=user.id,
        )
        db.add(item)
        db.flush()
        if item.status == "confirmed":
            _reject_competing_proposals(db, item, user.id)
        _notify_assignee(
            db,
            item,
            "收到新的人力预约",
            f"你收到 {item.start_time:%Y-%m-%d %H:%M} 至 "
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
