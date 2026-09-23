from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["报表"])


@router.get("/process")
def process_report(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project_id: int | None = None,
    owner_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    personnel_keyword: str | None = None,
    organization_keyword: str | None = None,
    personnel_scope: str | None = None,
    current_user: User = Depends(require_permission("process_report:view")),
    db: Session = Depends(get_db),
):
    return success(
        report_service.process_report(
            db,
            current_user,
            page,
            page_size,
            project_id=project_id,
            owner_id=owner_id,
            start_date=start_date,
            end_date=end_date,
            personnel_keyword=personnel_keyword,
            organization_keyword=organization_keyword,
            personnel_scope=personnel_scope,
        )
    )


@router.get("/workload")
def workload_report(
    start_date: date,
    end_date: date,
    department_id: int | None = None,
    user_id: int | None = None,
    current_user: User = Depends(require_permission("process_report:view")),
    db: Session = Depends(get_db),
):
    return success(report_service.workload_report(db, current_user, start_date, end_date, department_id, user_id))


@router.get("/workload-summary")
def workload_summary(
    start_date: date,
    end_date: date,
    granularity: str = "week",
    current_user: User = Depends(require_permission("analytics:view")),
    db: Session = Depends(get_db),
):
    return success(report_service.workload_summary(db, current_user, start_date, end_date, granularity))
