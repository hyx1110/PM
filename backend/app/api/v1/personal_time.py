from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.personal_time import PersonalTimeCreate
from app.services import personal_time_service

router = APIRouter(prefix="/personal-time-blocks", tags=["个人时间安排"])


@router.get("")
def list_personal_time_blocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: int | None = None,
    status: Literal["active", "withdrawn"] | None = None,
    sort_order: Literal["asc", "desc"] = "asc",
    current_user: User = Depends(require_permission("schedule:view")),
    db: Session = Depends(get_db),
):
    return success(
        personal_time_service.list_blocks(
            db,
            current_user,
            page,
            page_size,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            status=status,
            sort_order=sort_order,
        )
    )


@router.get("/mine")
def list_my_personal_time_blocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Literal["active", "withdrawn"] | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        personal_time_service.list_my_blocks(
            db, current_user, page, page_size, status=status
        )
    )


@router.post("")
def create_personal_time_block(
    payload: PersonalTimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(personal_time_service.create_block(db, payload, current_user))


@router.post("/{block_id}/withdraw")
def withdraw_personal_time_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        personal_time_service.withdraw_block(db, block_id, current_user)
    )
