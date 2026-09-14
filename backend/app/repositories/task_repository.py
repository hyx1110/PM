from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User


class TaskRepository:
    def get(self, db: Session, task_id: int) -> Task | None:
        return db.scalar(
            select(Task).where(Task.id == task_id, Task.is_deleted.is_(False))
        )

    @staticmethod
    def _booked_hours_expression():
        return (
            select(func.coalesce(func.sum(ScheduleBooking.planned_hours), 0))
            .where(
                ScheduleBooking.task_id == Task.id,
                ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
            )
            .correlate(Task)
            .scalar_subquery()
        )

    def detail(self, db: Session, task_id: int) -> dict | None:
        manager = aliased(User)
        row = db.execute(
            select(
                Task,
                Project.name.label("project_name"),
                User.name.label("owner_name"),
                manager.name.label("project_manager_name"),
                self._booked_hours_expression().label("booked_hours"),
            )
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == Task.owner_id)
            .join(manager, manager.id == Project.manager_id)
            .where(Task.id == task_id, Task.is_deleted.is_(False))
        ).first()
        if not row:
            return None
        task, project_name, owner_name, project_manager_name, booked_hours = row
        return {
            **{col.name: getattr(task, col.name) for col in Task.__table__.columns},
            "project_name": project_name,
            "owner_name": owner_name,
            "project_manager_name": project_manager_name,
            "booked_hours": booked_hours or 0,
        }

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        project_id: int | None = None,
        owner_id: int | None = None,
        status: str | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        filters = [Task.is_deleted.is_(False)]
        if project_id:
            filters.append(Task.project_id == project_id)
        if owner_id:
            filters.append(Task.owner_id == owner_id)
        if status == "delayed":
            filters.extend([Task.planned_end < datetime.now(), Task.status.notin_({"completed", "cancelled"})])
        elif status:
            filters.append(Task.status == status)
        if visible_project_ids is not None:
            filters.append(Task.project_id.in_(visible_project_ids or {-1}))
        total = db.scalar(select(func.count(Task.id)).where(*filters)) or 0
        manager = aliased(User)
        rows = db.execute(
            select(
                Task,
                Project.name.label("project_name"),
                User.name.label("owner_name"),
                manager.name.label("project_manager_name"),
                self._booked_hours_expression().label("booked_hours"),
            )
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == Task.owner_id)
            .join(manager, manager.id == Project.manager_id)
            .where(*filters)
            .order_by(Task.project_id, Task.parent_id, Task.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [
            {
                **{col.name: getattr(task, col.name) for col in Task.__table__.columns},
                "project_name": project_name,
                "owner_name": owner_name,
                "project_manager_name": project_manager_name,
                "booked_hours": booked_hours or 0,
            }
            for task, project_name, owner_name, project_manager_name, booked_hours in rows
        ], total


task_repository = TaskRepository()
