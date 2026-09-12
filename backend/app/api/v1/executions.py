from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.execution import ExecutionCreate, ExecutionUpdate
from app.services import execution_service

router = APIRouter(prefix="/executions", tags=["任务执行"])


@router.get("")
def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    task_id: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    mine: bool = False,
    current_user: User = Depends(require_permission("execution:view")),
    db: Session = Depends(get_db),
):
    return success(
        execution_service.list_executions(
            db,
            current_user,
            page,
            page_size,
            mine=mine,
            task_id=task_id,
            user_id=user_id,
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
        )
    )


@router.post("")
def create_execution(
    payload: ExecutionCreate,
    current_user: User = Depends(require_permission("execution:edit")),
    db: Session = Depends(get_db),
):
    item = execution_service.create_execution(db, payload, current_user)
    return success(execution_service.execution_detail(db, item.id, current_user))


@router.get("/{execution_id}")
def get_execution(
    execution_id: int,
    current_user: User = Depends(require_permission("execution:view")),
    db: Session = Depends(get_db),
):
    return success(execution_service.execution_detail(db, execution_id, current_user))


@router.put("/{execution_id}")
def update_execution(
    execution_id: int,
    payload: ExecutionUpdate,
    current_user: User = Depends(require_permission("execution:edit")),
    db: Session = Depends(get_db),
):
    execution_service.update_execution(db, execution_id, payload, current_user)
    return success(execution_service.execution_detail(db, execution_id, current_user))


@router.delete("/{execution_id}")
def delete_execution(
    execution_id: int,
    current_user: User = Depends(require_permission("execution:edit")),
    db: Session = Depends(get_db),
):
    execution_service.delete_execution(db, execution_id, current_user)
    return success(None)
