from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.organization import Department
from app.models.project import Project, ProjectMember
from app.models.schedule import ScheduleBooking
from app.models.user import User

BOOKED_HOUR_STATUSES = {"pending", "confirmed", "changed", "running", "completed"}


def booked_hours_expression():
    return (
        select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0))
        .where(
            ScheduleBooking.project_id == Project.id,
            ScheduleBooking.status.in_(BOOKED_HOUR_STATUSES),
        )
        .correlate(Project)
        .scalar_subquery()
    )


class ProjectRepository:
    def get(self, db: Session, project_id: int) -> Project | None:
        return db.scalar(select(Project).where(Project.id == project_id, Project.is_deleted.is_(False)))

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        keyword: str | None = None,
        status: str | None = None,
        manager_id: int | None = None,
        department_id: int | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        manager = aliased(User)
        creator = aliased(User)
        approver = aliased(User)
        booked_hours = booked_hours_expression()
        filters = [Project.is_deleted.is_(False)]
        if keyword:
            filters.append(or_(Project.name.like(f"%{keyword}%"), Project.code.like(f"%{keyword}%")))
        if status:
            filters.append(Project.status == status)
        if manager_id:
            filters.append(Project.manager_id == manager_id)
        if department_id:
            filters.append(Project.department_id == department_id)
        if visible_project_ids is not None:
            filters.append(Project.id.in_(visible_project_ids or {-1}))
        total = db.scalar(select(func.count(Project.id)).where(*filters)) or 0
        rows = db.execute(
            select(
                Project,
                manager.name.label("manager_name"),
                Department.name.label("department_name"),
                creator.name.label("creator_name"),
                approver.name.label("approver_name"),
                booked_hours.label("booked_hours"),
            )
            .join(manager, manager.id == Project.manager_id)
            .outerjoin(Department, Department.id == Project.department_id)
            .outerjoin(creator, creator.id == Project.created_by)
            .outerjoin(approver, approver.id == Project.approved_by)
            .where(*filters)
            .order_by(Project.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for project, manager_name, department_name, creator_name, approver_name, booked in rows:
            data = {col.name: getattr(project, col.name) for col in Project.__table__.columns}
            used = booked or 0
            data.update(
                manager_name=manager_name,
                department_name=department_name,
                creator_name=creator_name,
                approver_name=approver_name,
                booked_hours=used,
                remaining_hours=max(project.budget_hours - used, 0),
            )
            items.append(data)
        return items, total

    def list_members(self, db: Session, project_id: int, active_only: bool = True) -> list[dict]:
        statement = (
            select(ProjectMember, User.name.label("user_name"))
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
        )
        if active_only:
            statement = statement.where(ProjectMember.left_at.is_(None))
        rows = db.execute(statement.order_by(ProjectMember.joined_at)).all()
        return [
            {**{col.name: getattr(member, col.name) for col in ProjectMember.__table__.columns}, "user_name": user_name}
            for member, user_name in rows
        ]

    def visible_ids_for_user(self, db: Session, user_id: int) -> set[int]:
        managed = set(db.scalars(select(Project.id).where(Project.manager_id == user_id, Project.is_deleted.is_(False))).all())
        created = set(db.scalars(select(Project.id).where(Project.created_by == user_id, Project.is_deleted.is_(False))).all())
        member = set(
            db.scalars(
                select(ProjectMember.project_id).where(ProjectMember.user_id == user_id, ProjectMember.left_at.is_(None))
            ).all()
        )
        return managed | created | member


project_repository = ProjectRepository()
