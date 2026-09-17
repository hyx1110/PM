from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.notification import Notification
from app.models.schedule import ScheduleBooking
from app.services.notification_service import create_notification, dispatch_pending
from app.tasks.celery_app import celery_app
from app.utils.time import beijing_now


@celery_app.task(name="app.tasks.notification_tasks.create_upcoming_reminders")
def create_upcoming_reminders() -> dict:
    now = beijing_now()
    created = 0
    with SessionLocal() as db:
        bookings = db.scalars(
            select(ScheduleBooking)
            .where(
                ScheduleBooking.status.in_({"pending", "confirmed", "changed"}),
                ScheduleBooking.start_time > now,
                ScheduleBooking.start_time
                <= now + timedelta(hours=settings.notification_upcoming_hours),
            )
        ).all()
        for booking in bookings:
            exists = db.scalar(
                select(Notification.id).where(
                    Notification.recipient_id == booking.user_id,
                    Notification.event_type == "schedule_upcoming",
                    Notification.related_type == "schedule",
                    Notification.related_id == str(booking.id),
                )
            )
            if exists:
                continue
            create_notification(
                db,
                booking.user_id,
                "schedule_upcoming",
                "任务即将开始",
                f"预约 #{booking.id} 将于 {booking.start_time:%Y-%m-%d %H:%M} 开始。",
                level="warning",
                related_type="schedule",
                related_id=booking.id,
            )
            created += 1
        db.commit()
    return {"created": created}


@celery_app.task(name="app.tasks.notification_tasks.dispatch_external_notifications")
def dispatch_external_notifications() -> dict:
    with SessionLocal() as db:
        return dispatch_pending(db)
