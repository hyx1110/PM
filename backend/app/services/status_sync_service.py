from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.execution import ExecutionRecord
from app.models.project import Project
from app.models.task import Task


def _execution_derived_status(db: Session, task: Task) -> str:
    latest = db.scalar(
            select(ExecutionRecord).where(
                ExecutionRecord.task_id == task.id,
                ExecutionRecord.is_deleted.is_(False),
            )
            .order_by(ExecutionRecord.created_at.desc(), ExecutionRecord.id.desc())
            .limit(1)
    )
    if not latest:
        return "not_started"
    return {"completed": "completed", "paused": "suspended", "running": "running"}.get(latest.status, "not_started")


def synchronize_parent_status(db: Session, parent_id: int | None) -> None:
    if not parent_id:
        return
    parent = db.get(Task, parent_id)
    if not parent or parent.is_deleted or parent.status == "cancelled":
        return
    child_statuses = [
        status
        for status in db.scalars(
            select(Task.status).where(
                Task.parent_id == parent.id,
                Task.is_deleted.is_(False),
            )
        ).all()
        if status != "cancelled"
    ]
    if not child_statuses:
        parent.status = _execution_derived_status(db, parent)
        return
    if all(status == "completed" for status in child_statuses):
        parent.status = "completed"
    elif any(status == "running" for status in child_statuses):
        parent.status = "running"
    elif any(status == "suspended" for status in child_statuses):
        parent.status = "suspended"
    elif any(status == "completed" for status in child_statuses):
        # A parent with completed and not-started children has already begun;
        # reporting it as not_started would make progress move backwards.
        parent.status = "running"
    else:
        parent.status = "not_started"


def synchronize_project_status(db: Session, project_id: int) -> None:
    project = db.get(Project, project_id)
    if (
        not project
        or project.is_deleted
        or project.approval_status != "approved"
        or project.status == "Cancelled"
    ):
        return
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.project_id == project_id,
                Task.is_deleted.is_(False),
            )
        ).all()
    )
    # Completion is an explicit project-owner decision, never a task roll-up.
    if project.status == "Completed":
        return
    if not tasks:
        project.status = "Planned"
        project.actual_start = None
        project.actual_end = None
        return
    statuses = [task.status for task in tasks if task.status != "cancelled"]
    if any(status == "running" for status in statuses):
        project.status = "Running"
    elif any(status == "suspended" for status in statuses):
        project.status = "Suspended"
    elif any(status == "completed" for status in statuses):
        # Partially completed work means the project has started even when all
        # remaining tasks are still not_started.
        project.status = "Running"
    else:
        project.status = "Planned"
    actual_start, actual_end = db.execute(
        select(
            func.min(ExecutionRecord.actual_start),
            func.max(ExecutionRecord.actual_end),
        )
        .join(Task, Task.id == ExecutionRecord.task_id)
        .where(
            Task.project_id == project_id,
            Task.is_deleted.is_(False),
            ExecutionRecord.is_deleted.is_(False),
        )
    ).one()
    project.actual_start = actual_start
    project.actual_end = actual_end if project.status == "Completed" else None


def synchronize_task_status(db: Session, task_id: int) -> None:
    task = db.get(Task, task_id)
    if not task or task.is_deleted or task.status == "cancelled":
        return
    has_children = bool(
        db.scalar(
            select(Task.id).where(
                Task.parent_id == task.id,
                Task.is_deleted.is_(False),
            ).limit(1)
        )
    )
    if has_children:
        # A summary task follows its children. Direct execution records must not
        # overwrite a status already derived from the task hierarchy.
        synchronize_parent_status(db, task.id)
    else:
        task.status = _execution_derived_status(db, task)
    db.flush()
    synchronize_parent_status(db, task.parent_id)
    db.flush()
    synchronize_project_status(db, task.project_id)
    db.flush()
