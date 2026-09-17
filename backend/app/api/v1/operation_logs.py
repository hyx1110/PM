from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.exceptions import bad_request
from app.core.responses import success
from app.models.user import User
from app.repositories.operation_log_repository import operation_log_repository

router = APIRouter(prefix="/operation-logs", tags=["操作日志"])


@router.get("")
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    operator_id: int | None = None,
    module: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    _: User = Depends(require_permission("operation_log:view")),
    db: Session = Depends(get_db),
):
    if start_date and end_date and end_date < start_date:
        raise bad_request("结束日期不能早于开始日期")
    items, total = operation_log_repository.list(db, page, page_size, operator_id, module, start_date, end_date)
    return success({"items": items, "total": total, "page": page, "page_size": page_size})
