from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import success
from app.models.organization import Department
from app.models.user import User

router = APIRouter(prefix="/lookups", tags=["通用选项"])


@router.get("/users")
def user_options(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            User.id,
            User.username,
            User.name,
            User.department_id,
            User.organization_id,
        )
        .where(User.status == "active", User.is_deleted.is_(False))
        .order_by(User.name)
    ).all()
    return success([dict(row._mapping) for row in rows])


@router.get("/departments")
def department_options(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Department.id, Department.code, Department.name, Department.manager_id)
        .where(Department.status == "active")
        .order_by(Department.code)
    ).all()
    return success([dict(row._mapping) for row in rows])
