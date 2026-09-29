from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.work_calendar import WorkCalendarDayUpsert
from app.services import work_calendar_service
from app.utils.model import model_to_dict

router = APIRouter(prefix="/work-calendar", tags=["工作日历"])


@router.get("/planned-hours")
def estimate_planned_hours(
    start_date: date,
    end_date: date,
    member_count: int = Query(..., ge=1, le=100000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Defaults only: manually supplied budgets still use existing quota validation.
    # Inclusive dates, legal holidays and adjusted workdays use the same calendar
    # as booking validation. The company planning convention is 8 hours/person/day.
    workdays = work_calendar_service.count_workdays(db, start_date, end_date)
    return success({"workdays": workdays, "member_count": member_count,
                    "hours_per_day": 8, "planned_hours": workdays * member_count * 8})


@router.get("")
def list_calendar_days(
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(require_permission("schedule:view")),
    db: Session = Depends(get_db),
):
    items = work_calendar_service.list_calendar_days(db, year)
    return success([model_to_dict(item) for item in items])


@router.put("/{work_date}")
def upsert_calendar_day(
    work_date: date,
    payload: WorkCalendarDayUpsert,
    current_user: User = Depends(require_permission("calendar:manage")),
    db: Session = Depends(get_db),
):
    item = work_calendar_service.upsert_calendar_day(db, work_date, payload, current_user)
    return success(model_to_dict(item))


@router.delete("/{work_date}")
def delete_calendar_day(
    work_date: date,
    current_user: User = Depends(require_permission("calendar:manage")),
    db: Session = Depends(get_db),
):
    work_calendar_service.delete_calendar_day(db, work_date, current_user)
    return success(None)
