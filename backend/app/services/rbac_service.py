from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.organization import Department
from app.models.project import Project
from app.models.rbac import Permission, Role, UserRole
from app.models.user import User
from app.repositories.rbac_repository import rbac_repository
from app.services.operation_log_service import log_operation


def list_roles(db: Session) -> list[dict]:
    return rbac_repository.list_roles(db)


def list_permissions(db: Session):
    return [
        {column.name: getattr(item, column.name) for column in Permission.__table__.columns}
        for item in rbac_repository.list_permissions(db)
    ]


def ensure_default_system_role(db: Session, user_id: int) -> None:
    """Every active system identity must have at least one functional role."""
    # Explicitly assigned roles (also during imports) must be visible before
    # deciding whether the default role is missing; autoflush is disabled.
    db.flush()
    assignment_count = db.scalar(
        select(func.count(UserRole.id)).where(UserRole.user_id == user_id)
    ) or 0
    if assignment_count:
        return
    role = db.scalar(select(Role).where(Role.code == "project_member"))
    if not role:
        raise bad_request("系统项目成员角色尚未初始化，请先执行初始化脚本")
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.flush()


def validate_user_role_ids(
    db: Session,
    role_ids: list[int],
    *,
    operator_id: int,
    existing_user_id: int | None = None,
) -> list[int]:
    """Roles are additive; only an existing super admin can grant/revoke that role."""
    unique_ids = list(dict.fromkeys(role_ids))
    if unique_ids:
        found = set(db.scalars(select(Role.id).where(Role.id.in_(unique_ids))).all())
        if found != set(unique_ids):
            raise not_found("one or more roles do not exist")
    # Serialize super-admin grants/removals with the last-admin guard.
    super_role = db.scalar(select(Role).where(Role.code == "super_admin").with_for_update())
    currently_super = bool(super_role and existing_user_id and db.scalar(
        select(UserRole.id).where(UserRole.user_id == existing_user_id, UserRole.role_id == super_role.id)
        .with_for_update()
    ))
    will_be_super = bool(super_role and super_role.id in unique_ids)
    if will_be_super != currently_super:
        # A current read prevents a concurrent demotion from using stale roles.
        operator_is_super = db.scalar(
            select(UserRole.id).join(User, User.id == UserRole.user_id).where(
                UserRole.user_id == operator_id, UserRole.role_id == super_role.id,
                User.status == "active", User.is_deleted.is_(False),
            ).with_for_update()
        )
        if not operator_is_super:
            raise forbidden("只有超级管理员可以授予或移除超级管理员角色")
    return unique_ids


def assert_super_admin_continuity(
    db: Session,
    target_user: User,
    *,
    new_role_ids: list[int] | None = None,
    new_status: str | None = None,
    deleting: bool = False,
) -> None:
    """Keep at least one active, non-deleted super administrator."""
    if target_user.is_deleted or target_user.status != "active":
        return
    super_role = db.scalar(select(Role).where(Role.code == "super_admin").with_for_update())
    if not super_role:
        return
    currently_super = bool(
        db.scalar(
            select(UserRole.id).where(
                UserRole.user_id == target_user.id,
                UserRole.role_id == super_role.id,
            )
            .with_for_update()
        )
    )
    if not currently_super:
        return
    remains_active = not deleting and (new_status or target_user.status) == "active"
    remains_super = new_role_ids is None or super_role.id in set(new_role_ids)
    if remains_active and remains_super:
        return
    another_super_admin = db.scalar(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .where(
            UserRole.role_id == super_role.id,
            User.id != target_user.id,
            User.status == "active",
            User.is_deleted.is_(False),
        )
        .limit(1)
        .with_for_update()
    )
    if not another_super_admin:
        raise bad_request("不能移除、禁用或删除最后一个有效的超级管理员")


def update_role_permissions(db: Session, role_id: int, permission_ids: list[int], operator_id: int) -> dict:
    role = db.get(Role, role_id)
    if not role:
        raise not_found("role not found")
    existing_count = db.scalar(select(func.count(Permission.id)).where(Permission.id.in_(permission_ids or {-1}))) or 0
    if existing_count != len(set(permission_ids)):
        raise not_found("one or more permissions do not exist")
    before_role = next(
        item for item in rbac_repository.list_roles(db) if item["id"] == role_id
    )
    rbac_repository.replace_role_permissions(db, role_id, permission_ids)
    db.flush()
    log_operation(
        db,
        operator_id=operator_id,
        module="rbac",
        action="update_role_permissions",
        object_type="role",
        object_id=role_id,
        before_data={"permission_ids": sorted(before_role["permission_ids"])},
        after_data={"permission_ids": sorted(set(permission_ids))},
    )
    db.commit()
    return next(item for item in rbac_repository.list_roles(db) if item["id"] == role_id)


def assign_user_roles(db: Session, user_id: int, role_ids: list[int], operator_id: int) -> None:
    target_user = db.get(User, user_id)
    if not target_user or target_user.is_deleted:
        raise not_found("user not found")
    normalized_role_ids = validate_user_role_ids(db, role_ids, operator_id=operator_id, existing_user_id=user_id)
    new_role_codes = set(
        db.scalars(
            select(Role.code).where(Role.id.in_(normalized_role_ids or {-1}))
        ).all()
    )
    if not new_role_codes & {"super_admin", "department_manager", "functional_manager", "project_manager"} and db.scalar(
        select(Project.id).where(
            Project.manager_id == user_id,
            Project.is_deleted.is_(False),
            Project.status != "completed",
        ).limit(1)
    ):
        raise conflict(
            "用户仍负责未结束项目，须保留项目经理、职能主管、部门主管或超级管理员角色",
            40908,
            {"dependencies": ["active managed projects"]},
        )
    if "department_manager" not in new_role_codes and db.scalar(
        select(Department.id).where(Department.manager_id == user_id).limit(1)
    ):
        raise conflict(
            "用户仍是部门负责人，不能移除部门主管角色",
            40909,
            {"dependencies": ["managed departments"]},
        )
    previous_role_ids = list(
        db.scalars(
            select(UserRole.role_id)
            .where(UserRole.user_id == user_id)
            .order_by(UserRole.role_id)
        ).all()
    )
    assert_super_admin_continuity(
        db,
        target_user,
        new_role_ids=normalized_role_ids,
    )
    rbac_repository.replace_user_roles(db, user_id, normalized_role_ids)
    ensure_default_system_role(db, user_id)
    current_role_ids = list(
        db.scalars(
            select(UserRole.role_id)
            .where(UserRole.user_id == user_id)
            .order_by(UserRole.role_id)
        ).all()
    )
    log_operation(
        db,
        operator_id=operator_id,
        module="rbac",
        action="assign_user_roles",
        object_type="user",
        object_id=user_id,
        before_data={"role_ids": previous_role_ids},
        after_data={"role_ids": current_role_ids},
    )
    db.commit()
