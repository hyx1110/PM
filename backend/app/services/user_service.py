from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, not_found
from app.core.security import hash_password
from app.models.organization import Department, Organization
from app.models.rbac import Role
from app.models.user import User
from app.repositories.rbac_repository import rbac_repository
from app.repositories.user_repository import user_repository
from app.schemas.user import UserCreate, UserUpdate
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
    if supervisor_id and not db.get(User, supervisor_id):
        raise not_found("supervisor not found")


def list_users(db: Session, page: int, page_size: int, keyword: str | None, department_id: int | None, status: str | None):
    items, total = user_repository.list(db, page, page_size, keyword, department_id, status)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def user_detail(db: Session, user_id: int) -> dict:
    item = user_repository.detail(db, user_id)
    if not item:
        raise not_found("user not found")
    return item


def create_user(db: Session, payload: UserCreate, operator_id: int) -> User:
    if user_repository.get_by_username(db, payload.username):
        raise conflict("username already exists", 40902)
    if payload.email and db.scalar(select(User).where(User.email == payload.email)):
        raise conflict("email already exists", 40903)
    _validate_relations(db, payload.department_id, payload.organization_id, payload.supervisor_id)
    role_ids = list(set(payload.role_ids))
    if role_ids:
        found = set(db.scalars(select(Role.id).where(Role.id.in_(role_ids))).all())
        if found != set(role_ids):
            raise not_found("one or more roles do not exist")
    values = payload.model_dump(exclude={"password", "role_ids"})
    user = User(**values, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    rbac_repository.replace_user_roles(db, user.id, role_ids)
    log_operation(
        db,
        operator_id=operator_id,
        module="user",
        action="create",
        object_type="user",
        object_id=user.id,
        after_data={key: value for key, value in model_to_dict(user).items() if key != "password_hash"},
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate, operator_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise not_found("user not found")
    before = {key: value for key, value in model_to_dict(user).items() if key != "password_hash"}
    values = payload.model_dump(exclude_unset=True)
    role_ids = values.pop("role_ids", None)
    password = values.pop("password", None)

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
        rbac_repository.replace_user_roles(db, user_id, role_ids)
    db.flush()
    log_operation(
        db,
        operator_id=operator_id,
        module="user",
        action="update",
        object_type="user",
        object_id=user.id,
        before_data=before,
        after_data={key: value for key, value in model_to_dict(user).items() if key != "password_hash"},
    )
    db.commit()
    db.refresh(user)
    return user
