from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, not_found
from app.core.security import hash_password
from app.models.organization import Department, Organization
from app.models.employee_profile import EmployeeProfile
from app.models.project import Project, ProjectMember
from app.models.rbac import Role, UserRole
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.repositories.rbac_repository import rbac_repository
from app.repositories.user_repository import user_repository
from app.schemas.employee_profile import EmployeeProfileUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.employee_profile_service import (
    ensure_default_system_role,
    upsert_employee_profile,
)
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict


def _validate_relations(db: Session, department_id: int | None, organization_id: int | None, supervisor_id: int | None) -> None:
    if department_id and not db.get(Department, department_id):
        raise not_found("department not found")
    organization = db.get(Organization, organization_id) if organization_id else None
    if organization_id and not organization:
        raise not_found("organization not found")
    if organization and department_id and organization.department_id != department_id:
        raise bad_request("organization does not belong to the selected department")
    supervisor = db.get(User, supervisor_id) if supervisor_id else None
    if supervisor_id and (not supervisor or supervisor.is_deleted):
        raise not_found("supervisor not found")


def list_users(db: Session, page: int, page_size: int, keyword: str | None, department_id: int | None, status: str | None):
    items, total = user_repository.list(db, page, page_size, keyword, department_id, status)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def user_detail(db: Session, user_id: int) -> dict:
    item = user_repository.detail(db, user_id)
    if not item:
        raise not_found("user not found")
    return item


def _validate_role_ids(db: Session, role_ids: list[int]) -> list[int]:
    unique_ids = list(set(role_ids))
    if unique_ids:
        found = set(db.scalars(select(Role.id).where(Role.id.in_(unique_ids))).all())
        if found != set(unique_ids):
            raise not_found("one or more roles do not exist")
    return unique_ids


def create_user(db: Session, payload: UserCreate, operator_id: int) -> User:
    if user_repository.get_by_employee_no(db, payload.employee_no):
        raise conflict("employee_no already exists", 40902)
    if user_repository.get_by_username(db, payload.employee_no):
        raise conflict("login account already exists", 40902)
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
            "employee_profile",
        }
    )
    user = User(
        **values,
        employee_no=payload.employee_no,
        username=payload.employee_no,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    rbac_repository.replace_user_roles(db, user.id, role_ids)
    profile = upsert_employee_profile(db, user.id, payload.employee_profile)
    ensure_default_system_role(db, user.id)
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
            "employee_profile": model_to_dict(profile),
        },
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate, operator_id: int) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise not_found("user not found")
    before = {key: value for key, value in model_to_dict(user).items() if key != "password_hash"}
    values = payload.model_dump(exclude_unset=True)
    role_ids = values.pop("role_ids", None)
    employee_profile = values.pop("employee_profile", None)
    password = values.pop("password", None)
    values.pop("confirm_password", None)

    current_profile = db.scalar(
        select(EmployeeProfile).where(EmployeeProfile.user_id == user_id)
    )
    if current_profile and current_profile.data_source == "hrdb":
        hr_owned_fields = {
            "name",
            "email",
            "phone",
            "department_id",
            "organization_id",
            "supervisor_id",
        }
        if hr_owned_fields & values.keys() or employee_profile is not None:
            raise bad_request(
                "该用户由 HRDB 同步，姓名、组织、岗位和直属主管等主数据只读"
            )

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
    if supervisor_id == user_id:
        raise bad_request("user cannot be their own supervisor")
    _validate_relations(db, department_id, organization_id, supervisor_id)
    if values.get("email") and db.scalar(select(User.id).where(User.email == values["email"], User.id != user_id)):
        raise conflict("email already exists", 40903)
    for key, value in values.items():
        setattr(user, key, value)
    if password:
        user.password_hash = hash_password(password)
    if role_ids is not None:
        rbac_repository.replace_user_roles(
            db, user_id, _validate_role_ids(db, role_ids)
        )
    profile = None
    if employee_profile is not None:
        profile = upsert_employee_profile(
            db,
            user_id,
            EmployeeProfileUpdate.model_validate(employee_profile),
        )
    ensure_default_system_role(db, user_id)
    db.flush()
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
            **(
                {"employee_profile": model_to_dict(profile)}
                if profile
                else {}
            ),
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

    is_super_admin = db.scalar(
        select(UserRole.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.code == "super_admin")
        .limit(1)
    )
    if is_super_admin:
        another_super_admin = db.scalar(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.code == "super_admin",
                User.id != user_id,
                User.status == "active",
                User.is_deleted.is_(False),
            )
            .limit(1)
        )
        if not another_super_admin:
            raise bad_request("the last active super administrator cannot be deleted")

    dependencies: list[str] = []
    if db.scalar(
        select(Project.id)
        .where(
            Project.manager_id == user_id,
            Project.is_deleted.is_(False),
            Project.status.notin_({"Completed", "Cancelled"}),
        )
        .limit(1)
    ):
        dependencies.append("active projects")
    if db.scalar(
        select(Task.id)
        .join(Project, Project.id == Task.project_id)
        .where(
            Task.owner_id == user_id,
            Task.status.notin_({"completed", "cancelled"}),
            Project.is_deleted.is_(False),
            Project.status.notin_({"Completed", "Cancelled"}),
        )
        .limit(1)
    ):
        dependencies.append("active tasks")
    if db.scalar(
        select(ScheduleBooking.id)
        .join(Project, Project.id == ScheduleBooking.project_id)
        .where(
            ScheduleBooking.user_id == user_id,
            ScheduleBooking.status.in_({"draft", "pending", "confirmed", "changed", "running"}),
            Project.is_deleted.is_(False),
            Project.status.notin_({"Completed", "Cancelled"}),
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
            Project.status.notin_({"Completed", "Cancelled"}),
        )
        .limit(1)
    ):
        dependencies.append("active project memberships")
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
