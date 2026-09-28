from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.overtime import OvertimeCreate, OvertimeDecision
from app.services import overtime_service

router = APIRouter(prefix="/overtime", tags=["加班申请"])


@router.get("")
def list_requests(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    scope: str = "mine", status: str | None = None,
    user: User = Depends(require_permission("execution:view")), db: Session = Depends(get_db)):
    return success(overtime_service.list_requests(db, user, page, page_size, scope=scope, status=status))


@router.post("")
def create_request(payload: OvertimeCreate, user: User = Depends(require_permission("execution:edit")), db: Session = Depends(get_db)):
    return success(overtime_service.create_request(db, payload, user))


@router.get("/{request_id}")
def request_detail(request_id: int, user: User = Depends(require_permission("execution:view")), db: Session = Depends(get_db)):
    return success(overtime_service.request_detail(db, request_id, user))


@router.post("/{request_id}/approve")
def approve(request_id: int, payload: OvertimeDecision, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(overtime_service.decide_request(db, request_id, payload, user, True))


@router.post("/{request_id}/reject")
def reject(request_id: int, payload: OvertimeDecision, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(overtime_service.decide_request(db, request_id, payload, user, False))


@router.post("/{request_id}/withdraw")
def withdraw(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(overtime_service.withdraw_request(db, request_id, user))
