from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.execution import ExecutionRecord
from app.models.organization import Department, Organization
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


def task_actual_hours_expression():
    """Return cumulative active execution hours for the outer task row."""
    execution_total = aliased(ExecutionRecord)
    return (
        select(func.coalesce(func.sum(execution_total.actual_hours), 0))
        .where(
            execution_total.task_id == Task.id,
            execution_total.is_deleted.is_(False),
        )
        .correlate(Task)
        .scalar_subquery()
    )


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
                Task.estimated_hours,
                task_actual_hours_expression().label("task_actual_hours"),
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
        record, project_task_name, project_id, planned_start, planned_end, estimated_hours, task_actual_hours, project_name, user_name = row
        data = {
            col.name: getattr(record, col.name)
            for col in ExecutionRecord.__table__.columns
            if col.name != "exception_reason"
        }
        data.update(
            task_name=project_task_name,
            project_id=project_id,
            planned_start=planned_start,
            planned_end=planned_end,
            estimated_hours=estimated_hours,
            task_actual_hours=task_actual_hours,
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
        personnel_keyword: str | None = None,
        organization_keyword: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        visible_project_ids: set[int] | None = None,
        own_user_id: int | None = None,
        personnel_scope_user_ids: set[int] | None = None,
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
        if personnel_keyword and personnel_keyword.strip():
            pattern = f"%{personnel_keyword.strip()}%"
            filters.append(or_(User.name.like(pattern), User.employee_no.like(pattern)))
        if organization_keyword and organization_keyword.strip():
            pattern = f"%{organization_keyword.strip()}%"
            filters.append(or_(
                User.department_id.in_(select(Department.id).where(Department.name.like(pattern))),
                User.organization_id.in_(select(Organization.id).where(Organization.name.like(pattern))),
            ))
        if personnel_scope_user_ids is not None:
            filters.append(
                ExecutionRecord.user_id.in_(personnel_scope_user_ids or {-1})
            )
        if start_date:
            filters.append(
                func.coalesce(
                    ExecutionRecord.actual_end,
                    ExecutionRecord.actual_start,
                )
                >= start_date
            )
        if end_date:
            filters.append(ExecutionRecord.actual_start <= end_date)
        if visible_project_ids is not None:
            project_scope = Task.project_id.in_(visible_project_ids or {-1})
            filters.append(project_scope)
        if own_user_id is not None:
            filters.append(ExecutionRecord.user_id == own_user_id)
        count_query = (
            select(func.count(ExecutionRecord.id))
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == ExecutionRecord.user_id)
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
                Task.estimated_hours,
                task_actual_hours_expression().label("task_actual_hours"),
                Project.name.label("project_name"),
                User.name.label("user_name"),
            )
            .join(Task, Task.id == ExecutionRecord.task_id)
            .join(Project, Project.id == Task.project_id)
            .join(User, User.id == ExecutionRecord.user_id)
            .where(*filters)
            .order_by(ExecutionRecord.created_at.desc(), ExecutionRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = []
        for record, task_name, project_id_value, planned_start, planned_end, estimated_hours, task_actual_hours, project_name, user_name in rows:
            data = {
                col.name: getattr(record, col.name)
                for col in ExecutionRecord.__table__.columns
                if col.name != "exception_reason"
            }
            data.update(
                task_name=task_name,
                project_id=project_id_value,
                project_name=project_name,
                user_name=user_name,
                planned_start=planned_start,
                planned_end=planned_end,
                estimated_hours=estimated_hours,
                task_actual_hours=task_actual_hours,
            )
            items.append(data)
        return items, total


execution_repository = ExecutionRepository()
