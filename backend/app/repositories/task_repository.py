from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task
from app.models.user import User


class TaskRepository:
    def get(self, db: Session, task_id: int) -> Task | None:
        return db.get(Task, task_id)

    def detail(self, db: Session, task_id: int) -> dict | None:
        row = db.execute(
            select(Task, Project.name.label("project_name"), User.name.label("owner_name"))
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == Task.owner_id)
            .where(Task.id == task_id)
        ).first()
        if not row:
            return None
        task, project_name, owner_name = row
        return {
            **{col.name: getattr(task, col.name) for col in Task.__table__.columns},
            "project_name": project_name,
            "owner_name": owner_name,
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
        filters = []
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
        rows = db.execute(
            select(Task, Project.name.label("project_name"), User.name.label("owner_name"))
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == Task.owner_id)
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
            }
            for task, project_name, owner_name in rows
        ], total


task_repository = TaskRepository()
