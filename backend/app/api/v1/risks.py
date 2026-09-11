from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.risk import RiskHandleRequest
from app.services import risk_service

router = APIRouter(prefix="/risks", tags=["风险中心"])


@router.get("")
def list_risks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    risk_type: str | None = None,
    risk_level: str | None = None,
    project_id: int | None = None,
    user_id: int | None = None,
    current_user: User = Depends(require_permission("risk:view")),
    db: Session = Depends(get_db),
):
    return success(
        risk_service.list_risks(
            db,
            current_user,
            page,
            page_size,
            status=status,
            risk_type=risk_type,
            risk_level=risk_level,
            project_id=project_id,
            user_id=user_id,
        )
    )


@router.get("/stats")
def risk_stats(
    current_user: User = Depends(require_permission("risk:view")),
    db: Session = Depends(get_db),
):
    return success(risk_service.risk_stats(db, current_user))


@router.post("/sync")
def sync_risks(
    current_user: User = Depends(require_permission("risk:handle")),
    db: Session = Depends(get_db),
):
    return success(risk_service.sync_risks(db, current_user))


@router.post("/{risk_id}/handle")
def handle_risk(
    risk_id: int,
    payload: RiskHandleRequest,
    current_user: User = Depends(require_permission("risk:handle")),
    db: Session = Depends(get_db),
):
    return success(risk_service.handle_risk(db, risk_id, payload, current_user))
