from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.rbac import Permission, Role
from app.models.user import User
from app.repositories.rbac_repository import rbac_repository
from app.services.employee_profile_service import ensure_default_system_role
from app.services.operation_log_service import log_operation


def list_roles(db: Session) -> list[dict]:
    return rbac_repository.list_roles(db)


def list_permissions(db: Session):
    return [
        {column.name: getattr(item, column.name) for column in Permission.__table__.columns}
        for item in rbac_repository.list_permissions(db)
    ]


def update_role_permissions(db: Session, role_id: int, permission_ids: list[int], operator_id: int) -> dict:
    role = db.get(Role, role_id)
    if not role:
        raise not_found("role not found")
    existing_count = db.scalar(select(func.count(Permission.id)).where(Permission.id.in_(permission_ids or {-1}))) or 0
    if existing_count != len(set(permission_ids)):
        raise not_found("one or more permissions do not exist")
    before = rbac_repository.list_roles(db)
    rbac_repository.replace_role_permissions(db, role_id, permission_ids)
    db.flush()
    log_operation(
        db,
        operator_id=operator_id,
        module="rbac",
        action="update_role_permissions",
        object_type="role",
        object_id=role_id,
        before_data=next((item for item in before if item["id"] == role_id), None),
        after_data={"permission_ids": permission_ids},
    )
    db.commit()
    return next(item for item in rbac_repository.list_roles(db) if item["id"] == role_id)


def assign_user_roles(db: Session, user_id: int, role_ids: list[int], operator_id: int) -> None:
    target_user = db.get(User, user_id)
    if not target_user or target_user.is_deleted:
        raise not_found("user not found")
    existing_count = db.scalar(select(func.count(Role.id)).where(Role.id.in_(role_ids or {-1}))) or 0
    if existing_count != len(set(role_ids)):
        raise not_found("one or more roles do not exist")
    rbac_repository.replace_user_roles(db, user_id, role_ids)
    ensure_default_system_role(db, user_id)
    log_operation(
        db,
        operator_id=operator_id,
        module="rbac",
        action="assign_user_roles",
        object_type="user",
        object_id=user_id,
        after_data={"role_ids": role_ids},
    )
    db.commit()
