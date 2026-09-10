from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.organization import DepartmentCreate, DepartmentUpdate, OrganizationCreate, OrganizationUpdate
from app.services import organization_service
from app.utils.model import model_to_dict

router = APIRouter(tags=["组织"])


@router.get("/departments")
def departments(
    _: User = Depends(require_permission("organization:view")),
    db: Session = Depends(get_db),
):
    return success(organization_service.list_departments(db))


@router.post("/departments")
def create_department(
    payload: DepartmentCreate,
    current_user: User = Depends(require_permission("organization:edit")),
    db: Session = Depends(get_db),
):
    item = organization_service.create_department(db, payload, current_user.id)
    return success(model_to_dict(item))


@router.put("/departments/{department_id}")
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    current_user: User = Depends(require_permission("organization:edit")),
    db: Session = Depends(get_db),
):
    item = organization_service.update_department(db, department_id, payload, current_user.id)
    return success(model_to_dict(item))


@router.get("/organizations/tree")
def organizations_tree(
    department_id: int | None = None,
    _: User = Depends(require_permission("organization:view")),
    db: Session = Depends(get_db),
):
    return success(organization_service.organization_tree(db, department_id))


@router.post("/organizations")
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(require_permission("organization:edit")),
    db: Session = Depends(get_db),
):
    item = organization_service.create_organization(db, payload, current_user.id)
    return success(model_to_dict(item))


@router.put("/organizations/{organization_id}")
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    current_user: User = Depends(require_permission("organization:edit")),
    db: Session = Depends(get_db),
):
    item = organization_service.update_organization(db, organization_id, payload, current_user.id)
    return success(model_to_dict(item))

