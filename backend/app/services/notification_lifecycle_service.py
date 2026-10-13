"""Keep actionable approval notifications tied to the underlying request."""
from sqlalchemy import String, and_, cast, exists, or_, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.project import Project, ProjectResourceRequest
from app.models.task import Task


APPROVAL_EVENTS = {
    "task": "task_approval_pending",
    "project": "project_approval_required",
    "project_resource_request": "project_resources_approval_required",
}


def active_notification_predicate():
    # Cast business IDs to strings: malformed legacy related_id values must
    # never be converted to integers by the database.
    pending_task = exists(select(Task.id).join(Project, Project.id == Task.project_id).where(
        cast(Task.id, String) == Notification.related_id,
        Task.is_deleted.is_(False), Task.approval_status == "pending",
        Task.parent_id.is_(None), Project.status != "completed",
        Project.is_deleted.is_(False), Project.approval_status == "approved",
    ))
    pending_project = exists(select(Project.id).where(
        cast(Project.id, String) == Notification.related_id,
        Project.is_deleted.is_(False), Project.approval_status == "pending",
    ))
    pending_resources = exists(select(ProjectResourceRequest.id).join(
        Project, Project.id == ProjectResourceRequest.project_id,
    ).where(
        cast(ProjectResourceRequest.id, String) == Notification.related_id,
        ProjectResourceRequest.status == "pending",
        Project.is_deleted.is_(False), Project.approval_status == "approved",
    ))
    return or_(
        Notification.event_type.notin_(tuple(APPROVAL_EVENTS.values())),
        and_(Notification.event_type == APPROVAL_EVENTS["task"],
             Notification.related_type == "task", pending_task),
        and_(Notification.event_type == APPROVAL_EVENTS["project"],
             Notification.related_type == "project", pending_project),
        and_(Notification.event_type == APPROVAL_EVENTS["project_resource_request"],
             Notification.related_type == "project_resource_request", pending_resources),
    )


def retire_approval_notifications(db: Session, related_type: str, related_id: int) -> None:
    """Soft-delete only approval prompts, in the caller's business transaction.

    Persist retirement so an old prompt cannot reappear after resubmission.
    Approval results and other historical notifications remain available.
    """
    db.execute(update(Notification).where(
        Notification.related_type == related_type,
        Notification.related_id == str(related_id),
        Notification.event_type == APPROVAL_EVENTS[related_type],
        Notification.is_deleted.is_(False),
    ).values(is_deleted=True).execution_options(synchronize_session=False))
