from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import success
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChange, ProfileUpdate
from app.services.auth_service import change_password, login, update_profile, user_profile

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login_api(payload: LoginRequest, db: Session = Depends(get_db)):
    return success(login(db, payload))


@router.get("/me")
def me_api(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(user_profile(db, current_user))


@router.put("/me")
def update_me_api(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(update_profile(db, current_user, payload))


@router.put("/me/password")
def change_password_api(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, current_user, payload)
    return success(None, "密码修改成功")


@router.post("/logout")
def logout_api(_: User = Depends(get_current_user)):
    return success(None, "logged out")
