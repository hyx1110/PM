from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_permission_codes, get_role_codes
from app.core.exceptions import bad_request, conflict, unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChange, ProfileUpdate
from app.services.operation_log_service import log_operation
from app.utils.employee_no import normalize_employee_no


def user_profile(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "employee_no": user.employee_no,
        "name": user.name,
        "email": user.email,
        "department_id": user.department_id,
        "organization_id": user.organization_id,
        "supervisor_id": user.supervisor_id,
        "status": user.status,
        "roles": sorted(get_role_codes(db, user.id)),
        "permissions": sorted(get_permission_codes(db, user.id)),
    }


def login(db: Session, payload: LoginRequest) -> dict:
    normalized_employee_no = normalize_employee_no(payload.employee_no)
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
        raise unauthorized("用户名或密码错误")
    if user.status != "active":
        raise unauthorized("当前账号已被禁用，请联系管理员")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_profile(db, user),
    }


def update_profile(db: Session, user: User, payload: ProfileUpdate) -> dict:
    email = str(payload.email) if payload.email else None
    if email and db.scalar(
        select(User.id).where(User.email == email, User.id != user.id)
    ):
        raise conflict("email already exists", 40903)
    before = {"name": user.name, "email": user.email}
    user.name = payload.name.strip()
    user.email = email
    if not user.name:
        raise bad_request("姓名不能为空")
    db.flush()
    log_operation(
        db,
        operator_id=user.id,
        module="profile",
        action="update",
        object_type="user",
        object_id=user.id,
        before_data=before,
        after_data={"name": user.name, "email": user.email},
    )
    db.commit()
    db.refresh(user)
    return user_profile(db, user)


def change_password(db: Session, user: User, payload: PasswordChange) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise bad_request("当前密码不正确")
    user.password_hash = hash_password(payload.new_password)
    log_operation(
        db,
        operator_id=user.id,
        module="profile",
        action="change_password",
        object_type="user",
        object_id=user.id,
        after_data={"password_changed": True},
    )
    db.commit()
