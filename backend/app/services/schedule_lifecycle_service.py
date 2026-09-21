from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.services.notification_service import create_notification
from app.utils.time import beijing_now


def synchronize_schedule_statuses(
    db: Session,
    now: datetime | None = None,
) -> dict[str, int]:
    """Advance confirmed bookings according to Beijing business time."""
    current = now or beijing_now()
    self_confirmed = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time > current,
            ScheduleBooking.user_id == ScheduleBooking.created_by,
            ScheduleBooking.project_id.in_(
                select(Project.id).where(
                    Project.manager_id == ScheduleBooking.created_by,
                    Project.approval_status == "approved",
                    Project.status.notin_({"Completed", "Cancelled"}),
                    Project.is_deleted.is_(False),
                )
            ),
            ScheduleBooking.task_id.in_(
                select(Task.id).where(
                    Task.status != "completed",
                    Task.is_deleted.is_(False),
                )
            ),
        )
        .values(status="confirmed", rejection_reason=None, version=ScheduleBooking.version + 1)
    ).rowcount or 0
    completed = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status.in_({"confirmed", "running"}),
            ScheduleBooking.end_time <= current,
        )
        .values(status="completed", version=ScheduleBooking.version + 1)
    ).rowcount or 0
    expired_pending = db.execute(
        select(
            ScheduleBooking.id,
            ScheduleBooking.user_id,
            ScheduleBooking.created_by,
            ScheduleBooking.start_time,
            ScheduleBooking.end_time,
        ).where(
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time <= current,
        )
        .with_for_update()
    ).all()
    cancelled = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time <= current,
        )
        .values(
            status="cancelled",
            rejection_reason="预约结束前未完成确认，系统已自动取消",
            version=ScheduleBooking.version + 1,
        )
    ).rowcount or 0
    for booking in expired_pending:
        content = (
            f"预约 #{booking.id}（{booking.start_time:%Y-%m-%d %H:%M} 至 "
            f"{booking.end_time:%H:%M}）在结束前未完成确认，系统已自动取消。"
        )
        for recipient_id in {booking.created_by, booking.user_id}:
            create_notification(
                db,
                recipient_id=recipient_id,
                event_type="schedule_auto_cancelled",
                title="人力预约已自动取消",
                content=content,
                level="warning",
                related_type="schedule",
                related_id=booking.id,
            )
    running = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status == "confirmed",
            ScheduleBooking.start_time <= current,
            ScheduleBooking.end_time > current,
        )
        .values(status="running", version=ScheduleBooking.version + 1)
    ).rowcount or 0
    db.flush()
    return {
        "self_confirmed": self_confirmed,
        "running": running,
        "completed": completed,
        "cancelled": cancelled,
    }
