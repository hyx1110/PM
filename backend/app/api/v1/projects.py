from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectMemberCreate, ProjectUpdate
from app.services import project_service
from app.utils.model import model_to_dict

router = APIRouter(prefix="/projects", tags=["项目"])


@router.get("")
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: str | None = None,
    status: str | None = None,
    manager_id: int | None = None,
    department_id: int | None = None,
    current_user: User = Depends(require_permission("project:view")),
    db: Session = Depends(get_db),
):
    return success(project_service.list_projects(db, current_user, page, page_size, keyword, status, manager_id, department_id))


@router.post("")
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.create_project(db, payload, current_user)
    return success(project_service.project_detail(db, item.id, current_user))


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: User = Depends(require_permission("project:view")),
    db: Session = Depends(get_db),
):
    return success(project_service.project_detail(db, project_id, current_user))


@router.put("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    project_service.update_project(db, project_id, payload, current_user)
    return success(project_service.project_detail(db, project_id, current_user))


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    project_service.delete_draft_project(db, project_id, current_user)
    return success(None)


@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    current_user: User = Depends(require_permission("project:view")),
    db: Session = Depends(get_db),
):
    return success(project_service.list_members(db, project_id, current_user))


@router.post("/{project_id}/members")
def add_member(
    project_id: int,
    payload: ProjectMemberCreate,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.add_member(db, project_id, payload, current_user)
    return success(model_to_dict(item))


@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    project_service.remove_member(db, project_id, user_id, current_user)
    return success(None)

