from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import success
from app.models.user import User
from app.services.dashboard_service import dashboard_workbench
from app.services.report_service import dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["首页"])


@router.get("/summary")
def summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(dashboard_summary(db, current_user))


@router.get("/workbench")
def workbench(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current user's complete dashboard in one permission-scoped request."""
    return success(dashboard_workbench(db, current_user))
