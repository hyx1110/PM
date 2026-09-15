from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.models.evaluation import TaskEvaluation
from app.models.execution import ExecutionRecord
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User


class ReportRepository:
    def process_report(
        self,
        db: Session,
        page: int,
        page_size: int,
        project_id: int | None = None,
        owner_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> tuple[list[dict], int]:
        parent = aliased(Task)
        filters = [
            Task.is_deleted.is_(False),
            Task.project_id.in_(
                select(Project.id).where(Project.is_deleted.is_(False))
            ),
        ]
        if project_id:
            filters.append(Task.project_id == project_id)
        if owner_id:
            filters.append(Task.owner_id == owner_id)
        if start_date:
            filters.append(Task.planned_end >= datetime.combine(start_date, time.min))
        if end_date:
            filters.append(Task.planned_start < datetime.combine(end_date + timedelta(days=1), time.min))
        if visible_project_ids is not None:
            filters.append(Task.project_id.in_(visible_project_ids or {-1}))
        total = db.scalar(select(func.count(Task.id)).where(*filters)) or 0
        actual_start = func.min(ExecutionRecord.actual_start)
        actual_end = func.max(ExecutionRecord.actual_end)
        actual_hours = func.coalesce(func.sum(ExecutionRecord.actual_hours), 0)
        statement = (
            select(
                Project.id.label("project_id"),
                Project.name.label("project_name"),
                case((Task.parent_id.is_(None), Task.name), else_=parent.name).label("level1_task"),
                case((Task.parent_id.is_not(None), Task.name), else_=None).label("level2_task"),
                Task.id.label("task_id"),
                Task.owner_id,
                User.name.label("owner_name"),
                Task.planned_start,
                Task.planned_end,
                Task.estimated_hours,
                Task.status,
                actual_start.label("actual_start"),
                actual_end.label("actual_end"),
                actual_hours.label("actual_hours"),
                TaskEvaluation.achievement_rate,
                TaskEvaluation.achievement_quality,
            )
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == Task.owner_id)
            .outerjoin(parent, parent.id == Task.parent_id)
            .outerjoin(
                ExecutionRecord,
                (ExecutionRecord.task_id == Task.id)
                & (ExecutionRecord.is_deleted.is_(False)),
            )
            .outerjoin(TaskEvaluation, TaskEvaluation.task_id == Task.id)
            .where(*filters)
            .group_by(
                Project.id,
                Project.name,
                Task.id,
                Task.name,
                Task.parent_id,
                parent.name,
                Task.owner_id,
                User.name,
                Task.planned_start,
                Task.planned_end,
                Task.estimated_hours,
                Task.status,
                TaskEvaluation.achievement_rate,
                TaskEvaluation.achievement_quality,
            )
            .order_by(Project.id, Task.parent_id, Task.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [dict(row._mapping) for row in db.execute(statement).all()], total

    def workload(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        department_id: int | None = None,
        user_id: int | None = None,
        visible_project_ids: set[int] | None = None,
    ) -> list[dict]:
        filters = [
            ScheduleBooking.status.in_({"confirmed", "running", "completed"}),
            ScheduleBooking.project_id.in_(
                select(Project.id).where(Project.is_deleted.is_(False))
            ),
            ScheduleBooking.start_time >= datetime.combine(start_date, time.min),
            ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), time.min),
        ]
        if department_id:
            filters.append(User.department_id == department_id)
        if user_id:
            filters.append(ScheduleBooking.user_id == user_id)
        if visible_project_ids is not None:
            filters.append(ScheduleBooking.project_id.in_(visible_project_ids or {-1}))
        booking_date = func.date(ScheduleBooking.start_time)
        rows = db.execute(
            select(
                ScheduleBooking.user_id,
                User.name.label("user_name"),
                booking_date.label("date"),
                func.sum(ScheduleBooking.planned_hours).label("planned_hours"),
            )
            .join(User, User.id == ScheduleBooking.user_id)
            .where(*filters)
            .group_by(ScheduleBooking.user_id, User.name, booking_date)
            .order_by(booking_date, User.name)
        ).all()
        return [dict(row._mapping) for row in rows]


report_repository = ReportRepository()
