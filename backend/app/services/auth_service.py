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
    normalized_username = normalize_username(payload.username)
    user = db.scalar(select(User).where(User.username == normalized_username))
    # Fall back to the original value for accounts created before username
    # normalization was introduced.
    if not user and normalized_username != payload.username:
        user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise unauthorized("invalid username or password")
    if user.status != "active":
        raise unauthorized("account is disabled")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_profile(db, user),
    }
