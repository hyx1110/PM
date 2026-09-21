from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectDecision,
    ProjectResourceRequestCreate,
    ProjectUpdate,
)
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
    organization_id: int | None = None,
    employee_no: str | None = None,
    name: str | None = None,
    approval_status: str | None = None,
    approver_id: int | None = None,
    personnel_keyword: str | None = None,
    organization_keyword: str | None = None,
    manageable_only: bool = False,
    current_user: User = Depends(require_permission("project:view")),
    db: Session = Depends(get_db),
):
    return success(
        project_service.list_projects(
            db,
            current_user,
            page,
            page_size,
            keyword,
            status,
            manager_id,
            department_id,
            organization_id,
            employee_no,
            name,
            approval_status,
            approver_id,
            personnel_keyword,
            organization_keyword,
            manageable_only,
        )
    )


@router.post("")
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.create_project(db, payload, current_user)
    return success(project_service.project_detail(db, item.id, current_user))


@router.get("/resource-requests/pending")
def list_pending_resource_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(project_service.list_pending_resource_requests(db, current_user))


@router.get("/approvals/pending")
def list_pending_project_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(project_service.list_pending_project_approvals(db, current_user))


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: User = Depends(require_permission("project:view")),
    db: Session = Depends(get_db),
):
    return success(project_service.project_detail(db, project_id, current_user))


@router.post("/{project_id}/submit")
def submit_project(
    project_id: int,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    project_service.submit_project(db, project_id, current_user)
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


@router.post("/{project_id}/complete")
def complete_project(
    project_id: int,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    project_service.complete_project(db, project_id, current_user)
    return success(project_service.project_detail(db, project_id, current_user))


@router.post("/{project_id}/approve")
def approve_project(
    project_id: int,
    payload: ProjectDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = project_service.decide_project(
        db, project_id, payload, current_user, approved=True
    )
    return success(model_to_dict(item))


@router.post("/{project_id}/reject")
def reject_project(
    project_id: int,
    payload: ProjectDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = project_service.decide_project(
        db, project_id, payload, current_user, approved=False
    )
    return success(model_to_dict(item))


@router.get("/{project_id}/resource-requests")
def list_resource_requests(
    project_id: int,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    return success(project_service.list_resource_requests(db, project_id, current_user))


@router.post("/{project_id}/resource-requests")
def create_resource_request(
    project_id: int,
    payload: ProjectResourceRequestCreate,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.create_resource_request(db, project_id, payload, current_user)
    return success(model_to_dict(item))


@router.post("/{project_id}/resource-requests/{request_id}/approve")
def approve_resource_request(
    project_id: int,
    request_id: int,
    payload: ProjectDecision,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.decide_resource_request(
        db, project_id, request_id, payload, current_user, approved=True
    )
    return success(model_to_dict(item))


@router.post("/{project_id}/resource-requests/{request_id}/reject")
def reject_resource_request(
    project_id: int,
    request_id: int,
    payload: ProjectDecision,
    current_user: User = Depends(require_permission("project:edit")),
    db: Session = Depends(get_db),
):
    item = project_service.decide_resource_request(
        db, project_id, request_id, payload, current_user, approved=False
    )
    return success(model_to_dict(item))


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

