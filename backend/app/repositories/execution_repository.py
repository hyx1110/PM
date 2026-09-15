from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.execution import ExecutionRecord
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


class ExecutionRepository:
    def get(self, db: Session, execution_id: int) -> ExecutionRecord | None:
        return db.scalar(
            select(ExecutionRecord)
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .where(
                ExecutionRecord.id == execution_id,
                ExecutionRecord.is_deleted.is_(False),
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
            )
        )

    def detail(self, db: Session, execution_id: int) -> dict | None:
        row = db.execute(
            select(
                ExecutionRecord,
                Task.name.label("task_name"),
                Task.project_id,
                Task.planned_start,
                Task.planned_end,
                Project.name.label("project_name"),
                User.name.label("user_name"),
            )
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == ExecutionRecord.user_id)
            .where(
                ExecutionRecord.id == execution_id,
                ExecutionRecord.is_deleted.is_(False),
                Task.is_deleted.is_(False),
                Project.is_deleted.is_(False),
            )
        ).first()
        if not row:
            return None
        record, project_task_name, project_id, planned_start, planned_end, project_name, user_name = row
        data = {col.name: getattr(record, col.name) for col in ExecutionRecord.__table__.columns}
        data.update(
            task_name=project_task_name,
            project_id=project_id,
            planned_start=planned_start,
            planned_end=planned_end,
            project_name=project_name,
            user_name=user_name,
        )
        return data

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        task_id: int | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        visible_project_ids: set[int] | None = None,
        own_user_id: int | None = None,
    ) -> tuple[list[dict], int]:
        filters = [
            ExecutionRecord.is_deleted.is_(False),
            Task.is_deleted.is_(False),
            Project.is_deleted.is_(False),
        ]
        if task_id:
            filters.append(ExecutionRecord.task_id == task_id)
        if user_id:
            filters.append(ExecutionRecord.user_id == user_id)
        if project_id:
            filters.append(Task.project_id == project_id)
        if start_date:
            filters.append(ExecutionRecord.actual_start >= datetime.combine(start_date, time.min))
        if end_date:
            filters.append(ExecutionRecord.actual_start < datetime.combine(end_date + timedelta(days=1), time.min))
        if visible_project_ids is not None:
            project_scope = Task.project_id.in_(visible_project_ids or {-1})
            filters.append(
                or_(project_scope, ExecutionRecord.user_id == own_user_id)
                if own_user_id is not None
                else project_scope
            )
        count_query = (
            select(func.count(ExecutionRecord.id))
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .where(*filters)
        )
        total = db.scalar(count_query) or 0
        rows = db.execute(
            select(
                ExecutionRecord,
                Task.name.label("task_name"),
                Task.project_id,
                Task.planned_start,
                Task.planned_end,
                Project.name.label("project_name"),
                User.name.label("user_name"),
            )
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == ExecutionRecord.user_id)
            .where(*filters)
            .order_by(ExecutionRecord.actual_start.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for record, task_name, project_id_value, planned_start, planned_end, project_name, user_name in rows:
            data = {col.name: getattr(record, col.name) for col in ExecutionRecord.__table__.columns}
            data.update(
                task_name=task_name,
                project_id=project_id_value,
                project_name=project_name,
                user_name=user_name,
                planned_start=planned_start,
                planned_end=planned_end,
            )
            items.append(data)
        return items, total


execution_repository = ExecutionRepository()
