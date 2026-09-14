from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_role_codes
from app.models.project import Project, ProjectMember
from app.models.user import User


def visible_schedule_user_ids(db: Session, user: User) -> set[int] | None:
    """Resolve schedule visibility from system role, organization and projects."""
    roles = get_role_codes(db, user.id)
    if "super_admin" in roles:
        return None
    visible = {user.id}
    visible.update(
        db.scalars(
            select(User.id).where(
                User.supervisor_id == user.id,
                User.status == "active",
                User.is_deleted.is_(False),
            )
        ).all()
    )
    if roles & {"department_manager", "functional_manager"} and user.department_id:
        visible.update(
            db.scalars(
                select(User.id).where(
                    User.department_id == user.department_id,
                    User.status == "active",
                    User.is_deleted.is_(False),
                )
            ).all()
        )
    if "project_manager" in roles:
        managed_project_ids = select(Project.id).where(
            Project.manager_id == user.id,
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
