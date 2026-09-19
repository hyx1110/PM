from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskAssignee
from app.models.user import User


GLOBAL_PROJECT_ROLES = {"super_admin", "department_manager"}


def has_global_project_access(db: Session, user: User) -> bool:
    return bool(get_role_codes(db, user.id) & GLOBAL_PROJECT_ROLES)


def descendant_user_ids(db: Session, user_id: int) -> set[int]:
    """Walk every reporting level, stopping safely even with legacy cycles."""
    descendants: set[int] = set()
    visited = {user_id}
    frontier = {user_id}
    while frontier:
        children = set(db.scalars(select(User.id).where(
            User.supervisor_id.in_(frontier), User.is_deleted.is_(False)
        )).all()) - visited
        descendants.update(children)
        visited.update(children)
        frontier = children
    return descendants


def related_user_ids(db: Session, user: User) -> set[int] | None:
    roles = get_role_codes(db, user.id)
    if roles & GLOBAL_PROJECT_ROLES:
        return None
    return {user.id} | (descendant_user_ids(db, user.id) if "functional_manager" in roles else set())


def related_project_ids(db: Session, user_ids: set[int]) -> set[int]:
    if not user_ids:
        return set()
    managed = set(db.scalars(select(Project.id).where(
        Project.manager_id.in_(user_ids), Project.is_deleted.is_(False)
    )).all())
    members = set(db.scalars(select(ProjectMember.project_id).join(
        Project, Project.id == ProjectMember.project_id
    ).where(
        ProjectMember.user_id.in_(user_ids), ProjectMember.left_at.is_(None),
        Project.is_deleted.is_(False),
    )).all())
    assigned = set(db.scalars(select(Task.project_id).join(
        Project, Project.id == Task.project_id
    ).where(
        Task.is_deleted.is_(False), Project.is_deleted.is_(False),
        (Task.owner_id.in_(user_ids)) | Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id.in_(user_ids))),
    )).all())
    return managed | members | assigned


def visible_schedule_user_ids(db: Session, user: User) -> set[int] | None:
    """Resolve whose schedules the current user may see."""
    roles = get_role_codes(db, user.id)
    if roles & {"super_admin", "department_manager"}:
        return None
    visible = {user.id}
    if "functional_manager" in roles:
        visible.update(descendant_user_ids(db, user.id))
    if roles & {"project_manager", "functional_manager"}:
        managed_project_ids = select(Project.id).where(
            Project.manager_id == user.id,
            Project.approval_status == "approved",
            Project.status.notin_({"Completed", "Cancelled"}),
            Project.is_deleted.is_(False),
        )
        visible.update(
            db.scalars(
                select(ProjectMember.user_id).where(
                    ProjectMember.project_id.in_(managed_project_ids),
                    ProjectMember.left_at.is_(None),
                )
            ).all()
        )
    return visible
