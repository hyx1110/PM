from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request, conflict, forbidden, not_found
from app.models.organization import Department
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.repositories.project_repository import project_repository
from app.schemas.project import PROJECT_STATUSES, ProjectCreate, ProjectMemberCreate, ProjectUpdate
from app.services.operation_log_service import log_operation
from app.utils.model import model_to_dict


def visible_project_ids(db: Session, user: User) -> set[int] | None:
    roles = get_role_codes(db, user.id)
    if "super_admin" in roles:
        return None
    visible = project_repository.visible_ids_for_user(db, user.id)
    if roles & {"department_manager", "functional_manager"} and user.department_id:
        visible.update(
            db.scalars(
                select(Project.id).where(Project.department_id == user.department_id, Project.is_deleted.is_(False))
            ).all()
        )
    return visible


def assert_project_visible(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    scope = visible_project_ids(db, user)
    if scope is not None and project_id not in scope:
        raise forbidden("project is outside your data scope")
    return project


def assert_project_manageable(db: Session, project_id: int, user: User) -> Project:
    project = project_repository.get(db, project_id)
    if not project:
        raise not_found("project not found")
    roles = get_role_codes(db, user.id)
    allowed = "super_admin" in roles or project.manager_id == user.id
    if roles & {"department_manager", "functional_manager"}:
        allowed = allowed or (user.department_id is not None and project.department_id == user.department_id)
    if not allowed:
        raise forbidden("you cannot manage this project")
    return project


def list_projects(db: Session, user: User, page: int, page_size: int, keyword: str | None, status: str | None, manager_id: int | None, department_id: int | None):
    items, total = project_repository.list(
        db,
        page,
        page_size,
        keyword,
        status,
        manager_id,
        department_id,
        visible_project_ids(db, user),
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def project_detail(db: Session, project_id: int, user: User) -> dict:
    project = assert_project_visible(db, project_id, user)
    items, _ = project_repository.list(db, 1, 1, visible_project_ids={project.id})
    return items[0]


def create_project(db: Session, payload: ProjectCreate, user: User) -> Project:
    if db.scalar(select(Project.id).where(Project.code == payload.code)):
        raise conflict("project code already exists", 40921)
    if not db.get(User, payload.manager_id):
        raise not_found("project manager not found")
    if payload.department_id and not db.get(Department, payload.department_id):
        raise not_found("department not found")
    roles = get_role_codes(db, user.id)
    if not roles & {"super_admin", "department_manager", "functional_manager"} and payload.manager_id != user.id:
        raise forbidden("project managers may only create projects managed by themselves")
    if roles & {"department_manager", "functional_manager"} and user.department_id and payload.department_id != user.department_id:
        raise forbidden("department managers may only create projects in their own department")
    project = Project(**payload.model_dump())
    db.add(project)
    db.flush()
    log_operation(db, operator_id=user.id, module="project", action="create", object_type="project", object_id=project.id, after_data=model_to_dict(project))
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: int, payload: ProjectUpdate, user: User) -> Project:
    project = assert_project_manageable(db, project_id, user)
    before = model_to_dict(project)
    values = payload.model_dump(exclude_unset=True)
    if values.get("manager_id") and not db.get(User, values["manager_id"]):
        raise not_found("project manager not found")
    if values.get("department_id") and not db.get(Department, values["department_id"]):
        raise not_found("department not found")
    planned_start = values.get("planned_start", project.planned_start)
    planned_end = values.get("planned_end", project.planned_end)
    actual_start = values.get("actual_start", project.actual_start)
    actual_end = values.get("actual_end", project.actual_end)
    if planned_end < planned_start:
        raise bad_request("planned_end must be on or after planned_start")
    if actual_start and actual_end and actual_end < actual_start:
        raise bad_request("actual_end must be on or after actual_start")
    if values.get("status") and values["status"] not in PROJECT_STATUSES:
        raise bad_request("invalid project status")
    for key, value in values.items():
        setattr(project, key, value)
    db.flush()
    log_operation(db, operator_id=user.id, module="project", action="update", object_type="project", object_id=project.id, before_data=before, after_data=model_to_dict(project))
    db.commit()
    db.refresh(project)
    return project


def delete_draft_project(db: Session, project_id: int, user: User) -> None:
    project = assert_project_manageable(db, project_id, user)
    if project.status != "Draft":
        raise bad_request("only draft projects can be deleted")
    before = model_to_dict(project)
    project.is_deleted = True
    log_operation(db, operator_id=user.id, module="project", action="delete", object_type="project", object_id=project.id, before_data=before)
    db.commit()


def list_members(db: Session, project_id: int, user: User):
    assert_project_visible(db, project_id, user)
    return project_repository.list_members(db, project_id)


def add_member(db: Session, project_id: int, payload: ProjectMemberCreate, user: User) -> ProjectMember:
    assert_project_manageable(db, project_id, user)
    if not db.get(User, payload.user_id):
        raise not_found("user not found")
    member = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == payload.user_id)
    )
    if member and member.left_at is None:
        raise conflict("user is already an active project member", 40922)
    if member:
        member.left_at = None
        member.project_role = payload.project_role
        member.allocation_percent = payload.allocation_percent
        member.joined_at = payload.joined_at
    else:
        member = ProjectMember(project_id=project_id, **payload.model_dump())
        db.add(member)
    db.flush()
    log_operation(db, operator_id=user.id, module="project", action="add_member", object_type="project_member", object_id=member.id, after_data=model_to_dict(member))
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, project_id: int, member_user_id: int, user: User) -> None:
    assert_project_manageable(db, project_id, user)
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id,
            ProjectMember.left_at.is_(None),
        )
    )
    if not member:
        raise not_found("active project member not found")
    before = model_to_dict(member)
    member.left_at = datetime.now()
    log_operation(db, operator_id=user.id, module="project", action="remove_member", object_type="project_member", object_id=member.id, before_data=before, after_data=model_to_dict(member))
    db.commit()
