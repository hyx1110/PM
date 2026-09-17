from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_permission_codes, require_permission
from app.core.exceptions import forbidden
from app.core.responses import success
from app.models.user import User
from app.schemas.user import AssignRolesRequest, UserCreate, UserUpdate
from app.services import rbac_service, user_service

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: str | None = None,
    department_id: int | None = None,
    organization_id: int | None = None,
    status: str | None = None,
    _: User = Depends(require_permission("user:view")),
    db: Session = Depends(get_db),
):
    return success(user_service.list_users(db, page, page_size, keyword, department_id, organization_id, status))


@router.post("")
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_permission("user:edit")),
    db: Session = Depends(get_db),
):
    if payload.role_ids and "role:edit" not in get_permission_codes(
        db, current_user.id
    ):
        raise forbidden("创建用户时分配系统角色需要角色维护权限")
    user = user_service.create_user(db, payload, current_user.id)
    return success(user_service.user_detail(db, user.id))


@router.get("/{user_id}")
def get_user(
    user_id: int,
    _: User = Depends(require_permission("user:view")),
    db: Session = Depends(get_db),
):
    return success(user_service.user_detail(db, user_id))


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_permission("user:edit")),
    db: Session = Depends(get_db),
):
    if payload.role_ids is not None and "role:edit" not in get_permission_codes(
        db, current_user.id
    ):
        raise forbidden("修改用户系统角色需要角色维护权限")
    user_service.update_user(db, user_id, payload, current_user.id)
    return success(user_service.user_detail(db, user_id))


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_permission("user:edit")),
    db: Session = Depends(get_db),
):
    user_service.delete_user(db, user_id, current_user)
    return success(None)


@router.put("/{user_id}/roles")
def assign_roles(
    user_id: int,
    payload: AssignRolesRequest,
    current_user: User = Depends(require_permission("role:edit")),
    db: Session = Depends(get_db),
):
    rbac_service.assign_user_roles(db, user_id, payload.role_ids, current_user.id)
    return success(user_service.user_detail(db, user_id))
