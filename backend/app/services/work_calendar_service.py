from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request, not_found
from app.models.user import User
from app.models.work_calendar import WorkCalendarDay
from app.schemas.work_calendar import WorkCalendarDayUpsert
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict

MORNING_START = time(8, 30)
MORNING_END = time(12, 0)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(17, 30)


def list_calendar_days(db: Session, year: int) -> list[WorkCalendarDay]:
    return list(
        db.scalars(
            select(WorkCalendarDay)
            .where(
                WorkCalendarDay.work_date >= date(year, 1, 1),
                WorkCalendarDay.work_date <= date(year, 12, 31),
            )
            .order_by(WorkCalendarDay.work_date)
        ).all()
    )


def is_workday(db: Session, work_date: date) -> bool:
    override = db.scalar(
        select(WorkCalendarDay).where(WorkCalendarDay.work_date == work_date)
    )
    if override:
        return override.day_type == "workday"
    return work_date.weekday() < 5


def count_workdays(db: Session, start_date: date, end_date: date) -> int:
    """Count an inclusive range with one calendar query instead of one query per day."""
    if end_date < start_date:
        raise bad_request("结束日期不能早于开始日期")
    overrides = dict(
        db.execute(
            select(WorkCalendarDay.work_date, WorkCalendarDay.day_type).where(
                WorkCalendarDay.work_date >= start_date,
                WorkCalendarDay.work_date <= end_date,
            )
        ).all()
    )
    return sum(
        overrides.get(current_date, "workday" if current_date.weekday() < 5 else "holiday")
        == "workday"
        for current_date in (
            date.fromordinal(start_date.toordinal() + offset)
            for offset in range((end_date - start_date).days + 1)
        )
    )


def calculate_work_hours(db: Session, start_time: datetime, end_time: datetime) -> Decimal:
    if end_time <= start_time:
        raise bad_request("预约结束时间必须晚于开始时间")
    if start_time.date() != end_time.date():
        raise bad_request("一次人力预约必须在同一个工作日内完成")
    if any(
        value.second or value.microsecond or value.minute not in {0, 30}
        for value in (start_time, end_time)
    ):
        raise bad_request("预约时间必须按 30 分钟为单位选择")
    if not is_workday(db, start_time.date()):
        raise bad_request("所选日期不是工作日或属于法定节假日，不能预约")
    start_clock = start_time.time()
    end_clock = end_time.time()
    in_morning = MORNING_START <= start_clock < end_clock <= MORNING_END
    in_afternoon = AFTERNOON_START <= start_clock < end_clock <= AFTERNOON_END
    if not (in_morning or in_afternoon):
        raise bad_request("预约只能选择 08:30-12:00 或 13:00-17:30，且不能跨午休")
    minutes = int((end_time - start_time).total_seconds() // 60)
    return (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"))


def calculate_workday_hours(db: Session, start_date: date, end_date: date) -> Decimal:
    """Calculate normal work capacity for an inclusive date range."""
    workdays = count_workdays(db, start_date, end_date)
    return (
        Decimal(workdays) * Decimal(str(settings.standard_work_hours))
    ).quantize(Decimal("0.01"))


def upsert_calendar_day(
    db: Session,
    work_date: date,
    payload: WorkCalendarDayUpsert,
    user: User,
) -> WorkCalendarDay:
    item = db.scalar(
        select(WorkCalendarDay).where(WorkCalendarDay.work_date == work_date)
    )
    before = model_to_dict(item) if item else None
    if not item:
        item = WorkCalendarDay(work_date=work_date, **payload.model_dump())
        db.add(item)
    else:
        item.day_type = payload.day_type
        item.name = payload.name
        item.source = payload.source
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="work_calendar",
        action="create" if before is None else "update",
        object_type="work_calendar_day",
        object_id=item.id,
        before_data=before,
        after_data=model_to_dict(item),
    )
    db.commit()
    db.refresh(item)
    return item


def delete_calendar_day(db: Session, work_date: date, user: User) -> None:
    item = db.scalar(
        select(WorkCalendarDay).where(WorkCalendarDay.work_date == work_date)
    )
    if not item:
        raise not_found("work calendar override not found")
    before = model_to_dict(item)
    db.delete(item)
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="work_calendar",
        action="delete",
        object_type="work_calendar_day",
        object_id=item.id,
        before_data=before,
    )
    db.commit()
