from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, not_found
from app.models.organization import Department, Organization
from app.models.user import User
from app.repositories.organization_repository import organization_repository
from app.schemas.organization import DepartmentCreate, DepartmentUpdate, OrganizationCreate, OrganizationUpdate
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict


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
    _validate_department_l3(db, payload.manager_id)
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
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True)
    if "manager_id" in values:
        _validate_department_l3(db, values.get("manager_id"), department_id)
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
    if db.scalar(select(Organization.id).where(Organization.department_id == department_id).limit(1)):
        raise conflict("delete all organizations in the department before deleting it", 40913)
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
    nodes = {item["id"]: {**item, "children": []} for item in rows}
    roots: list[dict] = []
    for item in nodes.values():
        parent = nodes.get(item["parent_id"])
        if parent:
            parent["children"].append(item)
        else:
            roots.append(item)
    return roots


def create_organization(db: Session, payload: OrganizationCreate, operator_id: int) -> Organization:
    if not db.get(Department, payload.department_id):
        raise not_found("department not found")
    if db.scalar(select(Organization).where(Organization.department_id == payload.department_id, Organization.code == payload.code)):
        raise conflict("organization code already exists in department", 40912)
    parent = db.get(Organization, payload.parent_id) if payload.parent_id else None
    if parent and parent.department_id != payload.department_id:
        raise bad_request("parent organization must belong to the same department")
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
    before = model_to_dict(item)
    values = payload.model_dump(exclude_unset=True)
    parent_id = values.get("parent_id")
    if parent_id == organization_id:
        raise bad_request("organization cannot be its own parent")
    parent = db.get(Organization, parent_id) if parent_id else None
    if parent and parent.department_id != item.department_id:
        raise bad_request("parent organization must belong to the same department")
    cursor = parent
    while cursor:
        if cursor.id == organization_id:
            raise bad_request("organization hierarchy cannot contain a cycle")
        cursor = db.get(Organization, cursor.parent_id) if cursor.parent_id else None
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
