from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_permission_codes, get_role_codes
from app.core.exceptions import unauthorized
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.utils.username import normalize_username


def user_profile(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "employee_no": user.employee_no,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "department_id": user.department_id,
        "organization_id": user.organization_id,
        "status": user.status,
        "roles": sorted(get_role_codes(db, user.id)),
        "permissions": sorted(get_permission_codes(db, user.id)),
    }


def login(db: Session, payload: LoginRequest) -> dict:
    normalized_employee_no = normalize_username(payload.employee_no)
    user = db.scalar(
        select(User).where(
            User.employee_no == normalized_employee_no,
            User.is_deleted.is_(False),
        )
    )
    # Keep a fallback for employee numbers created before normalization was
    # introduced.
    if not user and normalized_employee_no != payload.employee_no:
        user = db.scalar(
            select(User).where(
                User.employee_no == payload.employee_no,
                User.is_deleted.is_(False),
            )
        )
    if not user or not verify_password(payload.password, user.password_hash):
        raise unauthorized("员工号或密码错误")
    if user.status != "active":
        raise unauthorized("当前账号已被禁用，请联系管理员")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_profile(db, user),
    }
