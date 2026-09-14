from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict
from app.models.employee_profile import EmployeeProfile
from app.models.rbac import Role, UserRole
from app.schemas.employee_profile import EmployeeProfileCreate, EmployeeProfileUpdate

HR_ROLE_CODE_BY_LEVEL = {
    "department_manager": "department_manager",
    "management_manager": "functional_manager",
}
HR_MANAGED_ROLE_CODES = set(HR_ROLE_CODE_BY_LEVEL.values())


def _assert_position_available(
    db: Session,
    position_id: str | None,
    user_id: int,
) -> None:
    if not position_id:
        return
    existing_user_id = db.scalar(
        select(EmployeeProfile.user_id).where(
            EmployeeProfile.position_id == position_id,
            EmployeeProfile.user_id != user_id,
        )
    )
    if existing_user_id:
        raise conflict("position_id already belongs to another employee", 40905)


def sync_hr_roles(db: Session, user_id: int, hr_management_level: str) -> None:
    required_code = HR_ROLE_CODE_BY_LEVEL.get(hr_management_level)
    roles = list(
        db.scalars(select(Role).where(Role.code.in_(HR_MANAGED_ROLE_CODES))).all()
    )
    role_by_code = {role.code: role for role in roles}
    if required_code and required_code not in role_by_code:
        raise bad_request("系统 L3/L4 角色尚未初始化，请先执行初始化脚本")

    existing = {
        item.role_id: item
        for item in db.scalars(
            select(UserRole).where(UserRole.user_id == user_id)
        ).all()
    }
    for code in HR_MANAGED_ROLE_CODES:
        role = role_by_code.get(code)
        if not role:
            continue
        assignment = existing.get(role.id)
        should_assign = code == required_code
        if should_assign:
            if assignment:
                assignment.is_hr_auto = True
            else:
                db.add(
                    UserRole(
                        user_id=user_id,
                        role_id=role.id,
                        is_manual=False,
                        is_hr_auto=True,
                    )
                )
        elif assignment and assignment.is_hr_auto:
            assignment.is_hr_auto = False
            if not assignment.is_manual:
                db.delete(assignment)


def ensure_default_system_role(db: Session, user_id: int) -> None:
    """Guarantee a usable system identity without confusing it with HR grade."""
    assignment_count = db.scalar(
        select(func.count(UserRole.id)).where(UserRole.user_id == user_id)
    ) or 0
    if assignment_count:
        return
    role = db.scalar(select(Role).where(Role.code == "project_member"))
    if not role:
        raise bad_request("系统项目成员角色尚未初始化，请先执行初始化脚本")
    db.add(
        UserRole(
            user_id=user_id,
            role_id=role.id,
            is_manual=True,
            is_hr_auto=False,
        )
    )
    db.flush()


def upsert_employee_profile(
    db: Session,
    user_id: int,
    payload: EmployeeProfileCreate | EmployeeProfileUpdate,
) -> EmployeeProfile:
    item = db.scalar(
        select(EmployeeProfile).where(EmployeeProfile.user_id == user_id)
    )
    values = payload.model_dump(exclude_unset=True)
    next_position_id = values.get("position_id", item.position_id if item else None)
    _assert_position_available(db, next_position_id, user_id)
    if not item:
        item = EmployeeProfile(user_id=user_id, **values)
        db.add(item)
    else:
        for key, value in values.items():
            setattr(item, key, value)
    db.flush()
    sync_hr_roles(db, user_id, item.hr_management_level)
    db.flush()
    return item
