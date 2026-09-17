from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.models.evaluation import TaskEvaluation
from app.models.execution import ExecutionRecord
from app.models.project import Project
from app.models.schedule import ScheduleBooking
from app.models.task import Task, TaskAssignee
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
            filters.append(
                Task.id.in_(
                    select(TaskAssignee.task_id).where(
                        TaskAssignee.user_id == owner_id
                    )
                )
            )
        if start_date:
            filters.append(Task.planned_end >= start_date)
        if end_date:
            filters.append(Task.planned_start <= end_date)
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
                Project.status.label("project_status"),
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
                TaskEvaluation.id.label("evaluation_id"),
                TaskEvaluation.evaluated_at,
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
                Project.status,
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
                TaskEvaluation.id,
                TaskEvaluation.evaluated_at,
            )
            .order_by(Project.id, Task.parent_id, Task.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [dict(row._mapping) for row in db.execute(statement).all()]
        task_ids = [item["task_id"] for item in items]
        if task_ids:
            assignee_rows = db.execute(
                select(TaskAssignee.task_id, User.name)
                .join(User, User.id == TaskAssignee.user_id)
                .where(TaskAssignee.task_id.in_(task_ids))
                .order_by(TaskAssignee.id)
            ).all()
            owner_names: dict[int, list[str]] = {}
            for task_id, owner_name in assignee_rows:
                owner_names.setdefault(task_id, []).append(owner_name)
            for item in items:
                item["owner_name"] = "、".join(
                    owner_names.get(item["task_id"], [item["owner_name"]])
                )
        return items, total

    def workload(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        department_id: int | None = None,
        user_id: int | None = None,
        visible_project_ids: set[int] | None = None,
        visible_user_ids: set[int] | None = None,
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
        if visible_user_ids is not None:
            filters.append(ScheduleBooking.user_id.in_(visible_user_ids or {-1}))
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
