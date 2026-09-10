from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.organization import Department
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User

ACTIVE_CONFLICT_STATUSES = {"pending", "confirmed", "changed", "running"}


class ScheduleRepository:
    def get(self, db: Session, schedule_id: int) -> ScheduleBooking | None:
        return db.get(ScheduleBooking, schedule_id)

    def detail(self, db: Session, schedule_id: int) -> dict | None:
        row = db.execute(
            select(
                ScheduleBooking,
                User.name.label("user_name"),
                User.department_id,
                Project.name.label("project_name"),
                Task.name.label("task_name"),
                Task.task_type,
            )
            .join(User, User.id == ScheduleBooking.user_id)
            .join(Project, Project.id == ScheduleBooking.project_id)
            .join(Task, Task.id == ScheduleBooking.task_id)
            .where(ScheduleBooking.id == schedule_id)
        ).first()
        if not row:
            return None
        item, user_name, department_id, project_name, task_name, task_type = row
        data = {col.name: getattr(item, col.name) for col in ScheduleBooking.__table__.columns}
        data.update(
            user_name=user_name,
            department_id=department_id,
            project_name=project_name,
            task_name=task_name,
            task_type=task_type,
            has_conflict=False,
        )
        return data

    def find_conflicts(
        self,
        db: Session,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_id: int | None = None,
    ) -> list[dict]:
        statement = (
            select(
                ScheduleBooking,
                Project.name.label("project_name"),
                Task.name.label("task_name"),
                User.name.label("user_name"),
            )
            .join(Project, Project.id == ScheduleBooking.project_id)
            .join(Task, Task.id == ScheduleBooking.task_id)
            .join(User, User.id == ScheduleBooking.user_id)
            .where(
                ScheduleBooking.user_id == user_id,
                ScheduleBooking.status.in_(ACTIVE_CONFLICT_STATUSES),
                ScheduleBooking.start_time < end_time,
                ScheduleBooking.end_time > start_time,
            )
        )
        if exclude_id:
            statement = statement.where(ScheduleBooking.id != exclude_id)
        rows = db.execute(statement.order_by(ScheduleBooking.start_time)).all()
        return [
            {
                "schedule_id": item.id,
                "project_id": item.project_id,
                "project_name": project_name,
                "task_id": item.task_id,
                "task_name": task_name,
                "user_id": item.user_id,
                "user_name": user_name,
                "start_time": item.start_time,
                "end_time": item.end_time,
            }
            for item, project_name, task_name, user_name in rows
        ]

    def list(
        self,
        db: Session,
        page: int,
        page_size: int,
        start_date: date | None = None,
        end_date: date | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
        department_id: int | None = None,
        status: str | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        filters = []
        if start_date:
            filters.append(ScheduleBooking.end_time > datetime.combine(start_date, time.min))
        if end_date:
            filters.append(ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), time.min))
        if user_id:
            filters.append(ScheduleBooking.user_id == user_id)
        if project_id:
            filters.append(ScheduleBooking.project_id == project_id)
        if task_id:
            filters.append(ScheduleBooking.task_id == task_id)
        if department_id:
            filters.append(User.department_id == department_id)
        if status:
            filters.append(ScheduleBooking.status == status)
        if visible_project_ids is not None:
            filters.append(ScheduleBooking.project_id.in_(visible_project_ids or {-1}))
        base = (
            select(ScheduleBooking)
            .join(User, User.id == ScheduleBooking.user_id)
            .where(*filters)
        )
        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = db.execute(
            select(
                ScheduleBooking,
                User.name.label("user_name"),
                User.department_id,
                Project.name.label("project_name"),
                Task.name.label("task_name"),
                Task.task_type,
            )
            .join(User, User.id == ScheduleBooking.user_id)
            .join(Project, Project.id == ScheduleBooking.project_id)
            .join(Task, Task.id == ScheduleBooking.task_id)
            .where(*filters)
            .order_by(ScheduleBooking.start_time, User.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for item, user_name, dept_id, project_name, task_name, task_type in rows:
            data = {col.name: getattr(item, col.name) for col in ScheduleBooking.__table__.columns}
            data.update(
                user_name=user_name,
                department_id=dept_id,
                project_name=project_name,
                task_name=task_name,
                task_type=task_type,
                has_conflict=False,
            )
            items.append(data)
        return items, total


schedule_repository = ScheduleRepository()
