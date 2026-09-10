from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.schemas.role import RolePermissionsUpdate
from app.services import rbac_service

router = APIRouter(tags=["角色权限"])


@router.get("/roles")
def roles(
    _: User = Depends(require_permission("role:view")),
    db: Session = Depends(get_db),
):
    return success(rbac_service.list_roles(db))


@router.get("/permissions")
def permissions(
    _: User = Depends(require_permission("role:view")),
    db: Session = Depends(get_db),
):
    return success(rbac_service.list_permissions(db))


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    current_user: User = Depends(require_permission("role:edit")),
    db: Session = Depends(get_db),
):
    return success(rbac_service.update_role_permissions(db, role_id, payload.permission_ids, current_user.id))

