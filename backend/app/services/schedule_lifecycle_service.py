from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.schedule import ScheduleBooking
from app.utils.time import beijing_now


def synchronize_schedule_statuses(
    db: Session,
    now: datetime | None = None,
) -> dict[str, int]:
    """Advance confirmed bookings according to Beijing business time."""
    current = now or beijing_now()
    completed = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status.in_({"confirmed", "running"}),
            ScheduleBooking.end_time <= current,
        )
        .values(status="completed", version=ScheduleBooking.version + 1)
    ).rowcount or 0
    cancelled = db.execute(
        update(ScheduleBooking)
        .where(
            ScheduleBooking.status.in_({"pending", "changed"}),
            ScheduleBooking.end_time <= current,
        )
        .values(status="cancelled", version=ScheduleBooking.version + 1)
    ).rowcount or 0
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
        "running": running,
        "completed": completed,
        "cancelled": cancelled,
    }
