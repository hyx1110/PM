from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.schedule import (
    ScheduleBatchCreate,
    ScheduleCopyWeek,
    ScheduleCreate,
    ScheduleDecision,
    ScheduleMove,
    ScheduleUpdate,
)
from app.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["人力预约"])


@router.get("")
def list_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    task_id: int | None = None,
    department_id: int | None = None,
    status: str | None = None,
    current_user: User = Depends(require_permission("schedule:view")),
    db: Session = Depends(get_db),
):
    return success(
        schedule_service.list_schedules(
            db,
            current_user,
            page,
            page_size,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            department_id=department_id,
            status=status,
        )
    )


@router.post("")
def create_schedule(
    payload: ScheduleCreate,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    item = schedule_service.create_schedule(db, payload, current_user)
    return success(schedule_service.schedule_detail(db, item.id, current_user))


@router.post("/batch")
def batch_create_schedules(
    payload: ScheduleBatchCreate,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    return success(schedule_service.batch_create_schedules(db, payload, current_user))


@router.post("/copy-week")
def copy_week(
    payload: ScheduleCopyWeek,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    return success(schedule_service.copy_week(db, payload, current_user))


@router.get("/my-pending")
def list_my_pending_schedules(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        schedule_service.list_my_pending_schedules(db, current_user, limit)
    )


@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: int,
    current_user: User = Depends(require_permission("schedule:view")),
    db: Session = Depends(get_db),
):
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    schedule_service.update_schedule(db, schedule_id, payload, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.post("/{schedule_id}/move")
def move_schedule(
    schedule_id: int,
    payload: ScheduleMove,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    schedule_service.move_schedule(db, schedule_id, payload, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    schedule_service.delete_schedule(db, schedule_id, current_user)
    return success(None)


@router.post("/{schedule_id}/submit")
def submit_schedule(
    schedule_id: int,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    schedule_service.submit_schedule(db, schedule_id, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.post("/{schedule_id}/withdraw")
def withdraw_schedule(
    schedule_id: int,
    current_user: User = Depends(require_permission("schedule:edit")),
    db: Session = Depends(get_db),
):
    schedule_service.withdraw_schedule(db, schedule_id, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.post("/{schedule_id}/confirm")
def confirm_schedule(
    schedule_id: int,
    payload: ScheduleDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule_service.confirm_schedule(db, schedule_id, payload, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))


@router.post("/{schedule_id}/reject")
def reject_schedule(
    schedule_id: int,
    payload: ScheduleDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule_service.reject_schedule(db, schedule_id, payload, current_user)
    return success(schedule_service.schedule_detail(db, schedule_id, current_user))
