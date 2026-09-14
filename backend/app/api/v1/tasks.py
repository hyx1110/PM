from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.get("")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    project_id: int | None = None,
    owner_id: int | None = None,
    status: str | None = None,
    current_user: User = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    return success(task_service.list_tasks(db, current_user, page, page_size, project_id, owner_id, status))


@router.post("")
def create_task(
    payload: TaskCreate,
    current_user: User = Depends(require_permission("task:edit")),
    db: Session = Depends(get_db),
):
    item = task_service.create_task(db, payload, current_user)
    return success(task_service.task_detail(db, item.id, current_user))


@router.get("/mine")
def list_my_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    current_user: User = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    return success(
        task_service.list_my_tasks(db, current_user, page, page_size, status)
    )


@router.get("/{task_id}")
def get_task(
    task_id: int,
    current_user: User = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    return success(task_service.task_detail(db, task_id, current_user))


@router.put("/{task_id}")
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: User = Depends(require_permission("task:edit")),
    db: Session = Depends(get_db),
):
    task_service.update_task(db, task_id, payload, current_user)
    return success(task_service.task_detail(db, task_id, current_user))


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(require_permission("task:edit")),
    db: Session = Depends(get_db),
):
    task_service.delete_task(db, task_id, current_user)
    return success(None)
