from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, not_found
from app.core.security import hash_password
from app.models.organization import Department, Organization
from app.models.project import Project, ProjectMember
from app.models.rbac import Role, UserRole
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.repositories.rbac_repository import rbac_repository
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate, UserUpdate
from app.services.operation_log_service import log_operation
from app.services.rbac_service import (
    assert_super_admin_continuity,
    ensure_default_system_role,
)
from app.utils.model import model_to_dict
from app.utils.personnel_scope import resolve_personnel_scope_user_ids
from app.utils.time import beijing_now


def _validate_relations(
    db: Session,
    department_id: int | None,
    organization_id: int | None,
    supervisor_id: int | None,
    current_user_id: int | None = None,
) -> None:
    department = db.get(Department, department_id) if department_id else None
    if department_id and not department:
        raise not_found("department not found")
    if department and department.status != "active":
        raise bad_request("不能把用户分配到已停用的部门")
    organization = db.get(Organization, organization_id) if organization_id else None
    if organization_id and not organization:
        raise not_found("organization not found")
    if organization and organization.status != "active":
        raise bad_request("不能把用户分配到已停用的组织")
    if organization and department_id and organization.department_id != department_id:
        raise bad_request("organization does not belong to the selected department")
    supervisor = db.get(User, supervisor_id) if supervisor_id else None
    if supervisor_id and (
        not supervisor or supervisor.is_deleted or supervisor.status != "active"
    ):
        raise not_found("supervisor not found")
    visited: set[int] = set()
    cursor = supervisor
    while cursor:
        if current_user_id is not None and cursor.id == current_user_id:
            raise bad_request("直属主管关系不能形成循环")
        if cursor.id in visited:
            raise bad_request("现有直属主管关系中存在循环，请先修正组织数据")
        visited.add(cursor.id)
        cursor = db.get(User, cursor.supervisor_id) if cursor.supervisor_id else None


def list_users(db: Session, page: int, page_size: int, keyword: str | None, department_id: int | None, organization_id: int | None, status: str | None, organization_keyword: str | None = None, personnel_scope: str | None = None):
    items, total = user_repository.list(
        db,
        page,
        page_size,
        keyword,
        department_id,
        organization_id,
        status,
        organization_keyword,
        personnel_scope_user_ids=resolve_personnel_scope_user_ids(db, personnel_scope),
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def user_detail(db: Session, user_id: int) -> dict:
    item = user_repository.detail(db, user_id)
    if not item:
        raise not_found("user not found")
    return item


def _validate_role_ids(
    db: Session,
    role_ids: list[int],
    *,
    existing_user_id: int | None = None,
) -> list[int]:
    unique_ids = list(dict.fromkeys(role_ids))
    if unique_ids:
        found = set(db.scalars(select(Role.id).where(Role.id.in_(unique_ids))).all())
        if found != set(unique_ids):
            raise not_found("one or more roles do not exist")
    super_role = db.scalar(select(Role).where(Role.code == "super_admin"))
    if super_role and super_role.id in unique_ids:
        already_super = bool(
            existing_user_id
            and db.scalar(
                select(UserRole.id)
                .where(
                    UserRole.user_id == existing_user_id,
                    UserRole.role_id == super_role.id,
                )
            )
        )
        if not already_super:
            raise bad_request("超级管理员只能在系统初始化时配置，不能通过用户管理新增")
    elif super_role and existing_user_id and db.scalar(
        select(UserRole.id).where(
            UserRole.user_id == existing_user_id,
            UserRole.role_id == super_role.id,
        )
    ):
        # This check intentionally also runs for an empty role list. Otherwise
        # an API client could bypass the UI guard and remove the initialized
        # super administrator by submitting role_ids=[].
        raise bad_request("初始化超级管理员角色受系统保护，不能通过用户管理移除")
    return unique_ids


def _collect_active_dependencies(
    db: Session,
    user_id: int,
    *,
    include_management_relations: bool = False,
) -> list[str]:
    dependencies: list[str] = []
    now = beijing_now()
    if db.scalar(
        select(Project.id)
        .where(
            Project.manager_id == user_id,
            Project.is_deleted.is_(False),
            Project.status != "completed",
        )
        .limit(1)
    ):
        dependencies.append("active projects")
    if db.scalar(
        select(Project.id).where(
            Project.approver_id == user_id,
            Project.approval_status == "pending",
            Project.is_deleted.is_(False),
        ).limit(1)
    ):
        dependencies.append("pending project approvals")
    if db.scalar(
        select(Task.id)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .join(Project, Project.id == Task.project_id)
        .where(
            TaskAssignee.user_id == user_id,
            Task.is_deleted.is_(False),
            Task.status != "completed",
            Project.is_deleted.is_(False),
            Project.status != "completed",
        )
        .limit(1)
    ):
        dependencies.append("active tasks")
    if db.scalar(
        select(ScheduleBooking.id)
        .join(Project, Project.id == ScheduleBooking.project_id)
        .where(
            ScheduleBooking.user_id == user_id,
            ScheduleBooking.status.in_(
                {"draft", "pending", "changed", "confirmed", "running"}
            ),
            ScheduleBooking.end_time > now,
            Project.is_deleted.is_(False),
            Project.status != "completed",
        )
        .limit(1)
    ):
        dependencies.append("active schedules")
    if db.scalar(
        select(ProjectMember.id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == user_id,
            ProjectMember.left_at.is_(None),
            Project.is_deleted.is_(False),
            Project.status != "completed",
        )
        .limit(1)
    ):
        dependencies.append("active project memberships")
    if include_management_relations:
        if db.scalar(
            select(User.id).where(
                User.supervisor_id == user_id,
                User.status == "active",
                User.is_deleted.is_(False),
            ).limit(1)
        ):
            dependencies.append("active direct reports")
        if db.scalar(
            select(Department.id).where(Department.manager_id == user_id).limit(1)
        ):
            dependencies.append("managed departments")
        if db.scalar(
            select(Organization.id).where(Organization.manager_id == user_id).limit(1)
        ):
            dependencies.append("managed organizations")
    return dependencies


def create_user(db: Session, payload: UserCreate, operator_id: int) -> User:
    if not payload.department_id:
        raise bad_request("新建用户必须选择所属部门")
    if not payload.supervisor_id:
        raise bad_request("新建用户必须选择直属主管；最高级主管由数据库维护")
    if user_repository.get_by_employee_no(db, payload.employee_no):
        raise conflict("employee_no already exists", 40902)
    if payload.email and db.scalar(select(User).where(User.email == payload.email)):
        raise conflict("email already exists", 40903)
    _validate_relations(db, payload.department_id, payload.organization_id, payload.supervisor_id)
    role_ids = _validate_role_ids(db, payload.role_ids)
    values = payload.model_dump(
        exclude={
            "employee_no",
            "password",
            "confirm_password",
            "role_ids",
        }
    )
    user = User(
        **values,
        employee_no=payload.employee_no,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    rbac_repository.replace_user_roles(db, user.id, role_ids)
    ensure_default_system_role(db, user.id)
    assigned_role_ids = list(
        db.scalars(
            select(UserRole.role_id)
            .where(UserRole.user_id == user.id)
            .order_by(UserRole.role_id)
        ).all()
    )
    log_operation(
        db,
        operator_id=operator_id,
        module="user",
        action="create",
        object_type="user",
        object_id=user.id,
        after_data={
            **{
                key: value
                for key, value in model_to_dict(user).items()
                if key != "password_hash"
            },
            "role_ids": assigned_role_ids,
        },
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate, operator_id: int) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise not_found("user not found")
    before = {
        **{
            key: value
            for key, value in model_to_dict(user).items()
            if key != "password_hash"
        },
        "role_ids": list(
            db.scalars(
                select(UserRole.role_id)
                .where(UserRole.user_id == user.id)
                .order_by(UserRole.role_id)
            ).all()
        ),
    }
    values = payload.model_dump(exclude_unset=True)
    role_ids = values.pop("role_ids", None)
    password = values.pop("password", None)
    values.pop("confirm_password", None)

    # A department change invalidates an old organization assignment when the
    # client does not explicitly send organization_id. This also keeps API
    # clients other than the web UI from leaving a stale cross-department link.
    if "department_id" in values and "organization_id" not in values and user.organization_id:
        current_organization = db.get(Organization, user.organization_id)
        if (
            not values["department_id"]
            or not current_organization
            or current_organization.department_id != values["department_id"]
        ):
            values["organization_id"] = None

    department_id = values.get("department_id", user.department_id)
    organization_id = values.get("organization_id", user.organization_id)
    supervisor_id = values.get("supervisor_id", user.supervisor_id)
    if user.supervisor_id and not supervisor_id:
        raise bad_request("不能清空直属主管；最高级主管由数据库维护")
    if not department_id:
        raise bad_request("用户必须具有所属部门")
    if supervisor_id == user_id:
        raise bad_request("user cannot be their own supervisor")
    _validate_relations(
        db,
        department_id,
        organization_id,
        supervisor_id,
        current_user_id=user_id,
    )
    if values.get("email") and db.scalar(select(User.id).where(User.email == values["email"], User.id != user_id)):
        raise conflict("email already exists", 40903)
    if any(values.get(key) is None for key in {"name", "status"} if key in values):
        raise bad_request("姓名和账号状态不能为空")
    normalized_role_ids = (
        _validate_role_ids(db, role_ids, existing_user_id=user_id)
        if role_ids is not None
        else None
    )
    if "department_id" in values and values["department_id"] != user.department_id:
        if db.scalar(
            select(Project.id).where(
                Project.manager_id == user.id,
                Project.department_id != values["department_id"],
                Project.is_deleted.is_(False),
                Project.status != "completed",
            ).limit(1)
        ):
            raise conflict(
                "用户仍负责其他部门的未结束项目，不能变更所属部门",
                40906,
                {"dependencies": ["active managed projects"]},
            )
        if db.scalar(
            select(Department.id).where(
                Department.manager_id == user.id,
                Department.id != values["department_id"],
            ).limit(1)
        ):
            raise conflict(
                "请先解除用户的部门主管负责人设置，再变更所属部门",
                40907,
                {"dependencies": ["managed departments"]},
            )
    if normalized_role_ids is not None:
        new_role_codes = set(
            db.scalars(
                select(Role.code).where(Role.id.in_(normalized_role_ids or {-1}))
            ).all()
        )
        if not new_role_codes & {"super_admin", "department_manager", "functional_manager", "project_manager"} and db.scalar(
            select(Project.id).where(
                Project.manager_id == user.id,
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
            select(Department.id).where(Department.manager_id == user.id).limit(1)
        ):
            raise conflict(
                "用户仍是部门负责人，不能移除部门主管角色",
                40909,
                {"dependencies": ["managed departments"]},
            )
    assert_super_admin_continuity(
        db,
        user,
        new_role_ids=normalized_role_ids,
        new_status=values.get("status", user.status),
    )
    if values.get("status") == "disabled" and user.status == "active":
        dependencies = _collect_active_dependencies(
            db,
            user.id,
            include_management_relations=True,
        )
        if dependencies:
            raise conflict(
                f"停用用户前请先处理：{', '.join(dependencies)}",
                40905,
                {"dependencies": dependencies},
            )
    for key, value in values.items():
        setattr(user, key, value)
    if password:
        user.password_hash = hash_password(password)
    if normalized_role_ids is not None:
        rbac_repository.replace_user_roles(db, user_id, normalized_role_ids)
    ensure_default_system_role(db, user_id)
    db.flush()
    assigned_role_ids = list(
        db.scalars(
            select(UserRole.role_id)
            .where(UserRole.user_id == user.id)
            .order_by(UserRole.role_id)
        ).all()
    )
    log_operation(
        db,
        operator_id=operator_id,
        module="user",
        action="update",
        object_type="user",
        object_id=user.id,
        before_data=before,
        after_data={
            **{
                key: value
                for key, value in model_to_dict(user).items()
                if key != "password_hash"
            },
            "role_ids": assigned_role_ids,
        },
    )
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int, operator: User) -> None:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise not_found("user not found")
    if user.id == operator.id:
        raise bad_request("users cannot delete their own account")
    assert_super_admin_continuity(db, user, deleting=True)

    dependencies = _collect_active_dependencies(
        db,
        user_id,
        include_management_relations=True,
    )
    if dependencies:
        raise conflict(
            f"reassign or close the user's {', '.join(dependencies)} before deleting",
            40904,
            {"dependencies": dependencies},
        )

    before = {key: value for key, value in model_to_dict(user).items() if key != "password_hash"}
    db.execute(update(Department).where(Department.manager_id == user_id).values(manager_id=None))
    db.execute(update(Organization).where(Organization.manager_id == user_id).values(manager_id=None))
    db.execute(update(User).where(User.supervisor_id == user_id).values(supervisor_id=None))
    rbac_repository.clear_user_roles(db, user_id)
    user.status = "disabled"
    user.is_deleted = True
    user.department_id = None
    user.organization_id = None
    user.supervisor_id = None
    db.flush()
    log_operation(
        db,
        operator_id=operator.id,
        module="user",
        action="delete",
        object_type="user",
        object_id=user.id,
        before_data=before,
        after_data={"status": user.status, "is_deleted": user.is_deleted},
    )
    db.commit()
