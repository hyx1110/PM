from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.models.project import Project, ProjectMember
from app.models.user import User


def visible_schedule_user_ids(db: Session, user: User) -> set[int] | None:
    """Resolve whose schedules the current user may see."""
    roles = get_role_codes(db, user.id)
    if roles & {"super_admin", "department_manager"}:
        return None
    visible = {user.id}
    if "functional_manager" in roles:
        direct_ids = set(db.scalars(select(User.id).where(User.supervisor_id == user.id, User.status == "active", User.is_deleted.is_(False))).all())
        visible.update(direct_ids)
        if direct_ids:
            visible.update(db.scalars(select(User.id).where(User.supervisor_id.in_(direct_ids), User.status == "active", User.is_deleted.is_(False))).all())
    if "project_manager" in roles:
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
