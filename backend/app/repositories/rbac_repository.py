from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole


class RBACRepository:
    def list_roles(self, db: Session) -> list[dict]:
        items: list[dict] = []
        for role in db.scalars(select(Role).order_by(Role.id)).all():
            permissions = db.execute(
                select(Permission.id, Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            ).all()
            data = {col.name: getattr(role, col.name) for col in Role.__table__.columns}
            data["permission_ids"] = [item.id for item in permissions]
            data["permissions"] = [item.code for item in permissions]
            items.append(data)
        return items

    def list_permissions(self, db: Session) -> list[Permission]:
        return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)).all())

    def replace_role_permissions(self, db: Session, role_id: int, permission_ids: list[int]) -> None:
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(synchronize_session=False)
        db.add_all([RolePermission(role_id=role_id, permission_id=item) for item in set(permission_ids)])

    def replace_user_roles(self, db: Session, user_id: int, role_ids: list[int]) -> None:
        requested = set(role_ids)
        existing = set(
            db.scalars(
                select(UserRole.role_id).where(UserRole.user_id == user_id)
            ).all()
        )
        if existing - requested:
            db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id.in_(existing - requested),
            ).delete(synchronize_session=False)
        db.add_all(
            [
                UserRole(user_id=user_id, role_id=role_id)
                for role_id in requested - existing
            ]
        )

    def clear_user_roles(self, db: Session, user_id: int) -> None:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete(
            synchronize_session=False
        )


rbac_repository = RBACRepository()
