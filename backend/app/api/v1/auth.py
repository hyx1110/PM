from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import success
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services.auth_service import login, user_profile

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login_api(payload: LoginRequest, db: Session = Depends(get_db)):
    return success(login(db, payload))


@router.get("/me")
def me_api(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success(user_profile(db, current_user))


@router.post("/logout")
def logout_api(_: User = Depends(get_current_user)):
    return success(None, "logged out")

