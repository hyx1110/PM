from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import forbidden, unauthorized
from app.core.security import decode_access_token
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise unauthorized("token is invalid or expired") from exc
    user = db.get(User, user_id)
    if not user or user.status != "active":
        raise unauthorized("user is disabled or does not exist")
    return user


def get_role_codes(db: Session, user_id: int) -> set[str]:
    statement = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(db.scalars(statement).all())


def get_permission_codes(db: Session, user_id: int) -> set[str]:
    roles = get_role_codes(db, user_id)
    if "super_admin" in roles:
        return set(db.scalars(select(Permission.code)).all())
    statement = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
        .distinct()
    )
    return set(db.scalars(statement).all())


def require_permission(permission_code: str) -> Callable:
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if permission_code not in get_permission_codes(db, current_user.id):
            raise forbidden(f"missing permission: {permission_code}")
        return current_user

    return dependency

