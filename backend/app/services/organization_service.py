from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, not_found
from app.models.organization import Department, Organization
from app.models.project import Project
from app.models.user import User
from app.repositories.organization_repository import organization_repository
from app.schemas.organization import DepartmentCreate, DepartmentUpdate, OrganizationCreate, OrganizationUpdate
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict


def _assert_locally_managed(item: Department | Organization) -> None:
    if item.data_source == "hrdb":
        raise bad_request("该数据来自 HRDB，只能通过同步任务更新")


def _validate_manager(db: Session, manager_id: int | None) -> None:
    manager = db.get(User, manager_id) if manager_id else None
    if manager_id and (not manager or manager.is_deleted or manager.status != "active"):
        raise not_found("manager not found")


def _validate_department_l3(
    db: Session, manager_id: int | None, department_id: int | None = None
) -> None:
    _validate_manager(db, manager_id)
    if manager_id:
        manager = db.get(User, manager_id)
        if "department_manager" not in get_role_codes(db, manager_id):
            raise bad_request("部门负责人必须具有 L3 角色")
        if department_id and manager.department_id != department_id:
            raise bad_request("L3 必须属于其负责的部门")


def list_departments(db: Session):
    return organization_repository.list_departments(db)


def create_department(db: Session, payload: DepartmentCreate, operator_id: int) -> Department:
    if db.scalar(select(Department).where(Department.code == payload.code)):
        raise conflict("department code already exists", 40911)
    if payload.manager_id:
        raise bad_request("请先创建部门并把 L3 用户分配到该部门，再设置部门负责人")
    item = Department(**payload.model_dump())
    db.add(item)
    db.flush()
    log_operation(db, operator_id=operator_id, module="organization", action="create_department", object_type="department", object_id=item.id, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def update_department(db: Session, department_id: int, payload: DepartmentUpdate, operator_id: int) -> Department:
    item = db.get(Department, department_id)
    if not item:
        raise not_found("department not found")
    _assert_locally_managed(item)
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True)
    if any(values.get(key) is None for key in {"name", "status"} if key in values):
        raise bad_request("部门名称和状态不能为空")
    if "manager_id" in values:
        _validate_department_l3(db, values.get("manager_id"), department_id)
    if values.get("status") == "disabled" and item.status != "disabled":
        dependencies: list[str] = []
        if db.scalar(
            select(User.id).where(
                User.department_id == department_id,
                User.status == "active",
                User.is_deleted.is_(False),
            ).limit(1)
        ):
            dependencies.append("启用用户")
        if db.scalar(
            select(Organization.id).where(
                Organization.department_id == department_id,
                Organization.status == "active",
            ).limit(1)
        ):
            dependencies.append("启用组织")
        if db.scalar(
            select(Project.id).where(
                Project.department_id == department_id,
                Project.is_deleted.is_(False),
                Project.status.notin_({"Completed", "Cancelled"}),
            ).limit(1)
        ):
            dependencies.append("未结束项目")
        if dependencies:
            raise conflict(
                f"停用部门前请先处理：{', '.join(dependencies)}",
                40915,
                {"dependencies": dependencies},
            )
    for key, value in values.items():
        setattr(item, key, value)
    db.flush()
    log_operation(db, operator_id=operator_id, module="organization", action="update_department", object_type="department", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def delete_department(db: Session, department_id: int, operator_id: int) -> None:
    item = db.get(Department, department_id)
    if not item:
        raise not_found("department not found")
    _assert_locally_managed(item)
    if db.scalar(select(Organization.id).where(Organization.department_id == department_id).limit(1)):
        raise conflict("delete all organizations in the department before deleting it", 40913)
    dependencies: list[str] = []
    if db.scalar(
        select(User.id).where(
            User.department_id == department_id,
            User.is_deleted.is_(False),
        ).limit(1)
    ):
        dependencies.append("users")
    if db.scalar(
        select(Project.id).where(
            Project.department_id == department_id,
            Project.is_deleted.is_(False),
        ).limit(1)
    ):
        dependencies.append("projects")
    if dependencies:
        raise conflict(
            "reassign the department's users and projects before deleting it",
            40916,
            {"dependencies": dependencies},
        )
    before = model_to_dict(item)
    db.delete(item)
    db.flush()
    log_operation(
        db,
        operator_id=operator_id,
        module="organization",
        action="delete_department",
        object_type="department",
        object_id=department_id,
        before_data=before,
    )
    db.commit()


def organization_tree(db: Session, department_id: int | None = None) -> list[dict]:
    rows = organization_repository.list_organizations(db, department_id)
    nodes = {item["id"]: {**item, "users": [], "children": []} for item in rows}
    if nodes:
        users = db.scalars(
            select(User).where(
                User.organization_id.in_(nodes.keys()),
                User.is_deleted.is_(False),
            ).order_by(User.name, User.employee_no)
        ).all()
        for user in users:
            nodes[user.organization_id]["users"].append(
                {
                    "id": user.id,
                    "employee_no": user.employee_no,
                    "name": user.name,
                    "status": user.status,
                }
            )
    roots: list[dict] = []
    for item in nodes.values():
        parent = nodes.get(item["parent_id"])
        if parent:
            parent["children"].append(item)
        else:
            roots.append(item)
    return roots


def create_organization(db: Session, payload: OrganizationCreate, operator_id: int) -> Organization:
    department = db.get(Department, payload.department_id)
    if not department:
        raise not_found("department not found")
    if department.status != "active":
        raise bad_request("不能在已停用的部门下创建组织")
    if db.scalar(select(Organization).where(Organization.department_id == payload.department_id, Organization.code == payload.code)):
        raise conflict("organization code already exists in department", 40912)
    parent = db.get(Organization, payload.parent_id) if payload.parent_id else None
    if payload.parent_id and not parent:
        raise not_found("parent organization not found")
    if parent and parent.department_id != payload.department_id:
        raise bad_request("parent organization must belong to the same department")
    if parent and parent.status != "active":
        raise bad_request("不能在已停用的组织下创建子组织")
    _validate_manager(db, payload.manager_id)
    item = Organization(**payload.model_dump())
    db.add(item)
    db.flush()
    log_operation(db, operator_id=operator_id, module="organization", action="create_organization", object_type="organization", object_id=item.id, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def update_organization(db: Session, organization_id: int, payload: OrganizationUpdate, operator_id: int) -> Organization:
    item = db.get(Organization, organization_id)
    if not item:
        raise not_found("organization not found")
    _assert_locally_managed(item)
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True)
    if any(values.get(key) is None for key in {"name", "level", "status"} if key in values):
        raise bad_request("组织名称、层级和状态不能为空")
    department = db.get(Department, item.department_id)
    if (
        values.get("status", item.status) == "active"
        and (not department or department.status != "active")
    ):
        raise bad_request("已停用部门下的组织不能启用")
    parent_id = values.get("parent_id", item.parent_id)
    if parent_id == organization_id:
        raise bad_request("organization cannot be its own parent")
    parent = db.get(Organization, parent_id) if parent_id else None
    if parent_id and not parent:
        raise not_found("parent organization not found")
    if parent and parent.department_id != item.department_id:
        raise bad_request("parent organization must belong to the same department")
    if parent and parent.status != "active" and values.get("status", item.status) == "active":
        raise bad_request("启用组织不能挂在已停用的父组织下")
    cursor = parent
    while cursor:
        if cursor.id == organization_id:
            raise bad_request("organization hierarchy cannot contain a cycle")
        cursor = db.get(Organization, cursor.parent_id) if cursor.parent_id else None
    if values.get("status") == "disabled" and item.status != "disabled":
        dependencies: list[str] = []
        if db.scalar(
            select(User.id).where(
                User.organization_id == organization_id,
                User.status == "active",
                User.is_deleted.is_(False),
            ).limit(1)
        ):
            dependencies.append("active users")
        if db.scalar(
            select(Organization.id).where(
                Organization.parent_id == organization_id,
                Organization.status == "active",
            ).limit(1)
        ):
            dependencies.append("active child organizations")
        if dependencies:
            raise conflict(
                "停用组织前请先处理其中的启用用户和子组织",
                40917,
                {"dependencies": dependencies},
            )
    if "manager_id" in values:
        _validate_manager(db, values.get("manager_id"))
    for key, value in values.items():
        setattr(item, key, value)
    db.flush()
    log_operation(db, operator_id=operator_id, module="organization", action="update_organization", object_type="organization", object_id=item.id, before_data=before, after_data=model_to_dict(item))
    db.commit()
    db.refresh(item)
    return item


def delete_organization(db: Session, organization_id: int, operator_id: int) -> None:
    item = db.get(Organization, organization_id)
    if not item:
        raise not_found("organization not found")
    _assert_locally_managed(item)
    if organization_repository.has_children(db, organization_id):
        raise conflict("delete child organizations before deleting this organization", 40914)
    before = model_to_dict(item)
    db.delete(item)
    db.flush()
    log_operation(
        db,
        operator_id=operator_id,
        module="organization",
        action="delete_organization",
        object_type="organization",
        object_id=organization_id,
        before_data=before,
    )
    db.commit()
