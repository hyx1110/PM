from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.services.risk_service import sync_risks
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.risk_tasks.scan_project_risks")
def scan_project_risks() -> dict:
    with SessionLocal() as db:
        system_user = db.scalar(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.code == "super_admin",
                User.status == "active",
                User.is_deleted.is_(False),
            )
            .order_by(User.id)
        )
        if not system_user:
            return {"skipped": True, "reason": "no active super administrator"}
        return sync_risks(db, system_user)
