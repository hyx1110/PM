from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

PERMISSIONS = {
    "dashboard:view": ("查看首页", "dashboard"),
    "user:view": ("查看用户", "user"),
    "user:edit": ("维护用户", "user"),
    "organization:view": ("查看组织", "organization"),
    "organization:edit": ("维护组织", "organization"),
    "role:view": ("查看角色权限", "rbac"),
    "role:edit": ("维护角色权限", "rbac"),
    "project:view": ("查看项目", "project"),
    "project:edit": ("维护项目", "project"),
    "task:view": ("查看任务", "task"),
    "task:edit": ("维护任务", "task"),
    "schedule:view": ("查看共享看板", "schedule"),
    "schedule:edit": ("维护人力预约", "schedule"),
    "execution:view": ("查看任务执行", "execution"),
    "execution:edit": ("填写任务执行", "execution"),
    "process_report:view": ("查看项目过程报表", "report"),
    "evaluation:edit": ("维护达成评价", "evaluation"),
    "operation_log:view": ("查看操作日志", "operation_log"),
}

ROLES = {
    "super_admin": ("超级管理员", set(PERMISSIONS)),
    "department_manager": (
        "部门主管",
        {
            "dashboard:view", "user:view", "organization:view", "role:view", "project:view", "project:edit",
            "task:view", "task:edit", "schedule:view", "schedule:edit", "execution:view", "execution:edit",
            "process_report:view", "evaluation:edit", "operation_log:view",
        },
    ),
    "functional_manager": (
        "职能主管",
        {
            "dashboard:view", "user:view", "organization:view", "project:view", "project:edit", "task:view",
            "task:edit", "schedule:view", "schedule:edit", "execution:view", "process_report:view",
            "evaluation:edit",
        },
    ),
    "project_manager": (
        "项目经理",
        {
            "dashboard:view", "project:view", "project:edit", "task:view", "task:edit",
            "schedule:view", "schedule:edit", "execution:view", "execution:edit", "process_report:view",
            "evaluation:edit",
        },
    ),
    "project_member": (
        "项目成员",
        {"dashboard:view", "project:view", "task:view", "schedule:view", "execution:view", "execution:edit"},
    ),
}


def initialize() -> None:
    with SessionLocal() as db:
        permission_map: dict[str, Permission] = {}
        for code, (name, module) in PERMISSIONS.items():
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if not permission:
                permission = Permission(code=code, name=name, module=module)
                db.add(permission)
                db.flush()
            permission_map[code] = permission

        role_map: dict[str, Role] = {}
        for code, (name, permission_codes) in ROLES.items():
            role = db.scalar(select(Role).where(Role.code == code))
            if not role:
                role = Role(code=code, name=name, is_system=True)
                db.add(role)
                db.flush()
            role_map[code] = role
            db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
            db.add_all(
                [RolePermission(role_id=role.id, permission_id=permission_map[item].id) for item in permission_codes]
            )

        admin = db.scalar(select(User).where(User.username == settings.initial_admin_username))
        if not admin:
            admin = User(
                username=settings.initial_admin_username,
                password_hash=hash_password(settings.initial_admin_password),
                name=settings.initial_admin_name,
                status="active",
            )
            db.add(admin)
            db.flush()
        super_role = role_map["super_admin"]
        if not db.scalar(select(UserRole).where(UserRole.user_id == admin.id, UserRole.role_id == super_role.id)):
            db.add(UserRole(user_id=admin.id, role_id=super_role.id))
        db.commit()


if __name__ == "__main__":
    initialize()
