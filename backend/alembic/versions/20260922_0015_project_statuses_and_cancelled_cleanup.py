"""Normalize project statuses and physically remove cancelled projects.

Revision ID: 20260922_0015
Revises: 20260921_0014
Create Date: 2026-09-22

The cancelled-project cleanup is intentionally irreversible: downgrade can
restore the legacy status vocabulary, but cannot recreate deleted business
records.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0015"
down_revision: str | None = "20260921_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ids(bind, table: sa.Table, condition) -> list[int]:
    return list(bind.scalars(sa.select(table.c.id).where(condition)).all())


def _delete_related_notifications(
    bind,
    notifications: sa.Table,
    related_type: str,
    related_ids: list[int],
) -> None:
    if not related_ids:
        return
    bind.execute(
        notifications.delete().where(
            notifications.c.related_type == related_type,
            notifications.c.related_id.in_([str(item_id) for item_id in related_ids]),
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(
        bind=bind,
        only=[
            "projects",
            "project_members",
            "project_resource_requests",
            "tasks",
            "task_assignees",
            "task_evaluations",
            "execution_records",
            "schedule_bookings",
            "risk_records",
            "notifications",
        ],
    )
    projects = metadata.tables["projects"]
    project_members = metadata.tables["project_members"]
    resource_requests = metadata.tables["project_resource_requests"]
    tasks = metadata.tables["tasks"]
    task_assignees = metadata.tables["task_assignees"]
    task_evaluations = metadata.tables["task_evaluations"]
    execution_records = metadata.tables["execution_records"]
    schedules = metadata.tables["schedule_bookings"]
    risks = metadata.tables["risk_records"]
    notifications = metadata.tables["notifications"]

    cancelled_project_ids = _ids(
        bind,
        projects,
        sa.func.lower(projects.c.status) == "cancelled",
    )
    if cancelled_project_ids:
        cancelled_task_ids = _ids(
            bind,
            tasks,
            tasks.c.project_id.in_(cancelled_project_ids),
        )
        cancelled_schedule_ids = _ids(
            bind,
            schedules,
            schedules.c.project_id.in_(cancelled_project_ids),
        )
        cancelled_resource_ids = _ids(
            bind,
            resource_requests,
            resource_requests.c.project_id.in_(cancelled_project_ids),
        )
        risk_condition = risks.c.project_id.in_(cancelled_project_ids)
        if cancelled_task_ids:
            risk_condition = sa.or_(
                risk_condition,
                risks.c.task_id.in_(cancelled_task_ids),
            )
        cancelled_risk_ids = _ids(bind, risks, risk_condition)

        _delete_related_notifications(
            bind, notifications, "project", cancelled_project_ids
        )
        _delete_related_notifications(bind, notifications, "task", cancelled_task_ids)
        _delete_related_notifications(
            bind, notifications, "schedule", cancelled_schedule_ids
        )
        _delete_related_notifications(
            bind,
            notifications,
            "project_resource_request",
            cancelled_resource_ids,
        )
        _delete_related_notifications(bind, notifications, "risk", cancelled_risk_ids)

        # Break the self-reference before deleting an arbitrary-depth task tree.
        bind.execute(
            tasks.update()
            .where(tasks.c.project_id.in_(cancelled_project_ids))
            .values(parent_id=None)
        )
        if cancelled_task_ids:
            bind.execute(
                task_evaluations.delete().where(
                    task_evaluations.c.task_id.in_(cancelled_task_ids)
                )
            )
            bind.execute(
                execution_records.delete().where(
                    execution_records.c.task_id.in_(cancelled_task_ids)
                )
            )
            bind.execute(
                task_assignees.delete().where(
                    task_assignees.c.task_id.in_(cancelled_task_ids)
                )
            )
        if cancelled_risk_ids:
            bind.execute(risks.delete().where(risks.c.id.in_(cancelled_risk_ids)))
        if cancelled_schedule_ids:
            bind.execute(
                schedules.delete().where(schedules.c.id.in_(cancelled_schedule_ids))
            )
        if cancelled_task_ids:
            bind.execute(tasks.delete().where(tasks.c.id.in_(cancelled_task_ids)))
        bind.execute(
            project_members.delete().where(
                project_members.c.project_id.in_(cancelled_project_ids)
            )
        )
        bind.execute(
            resource_requests.delete().where(
                resource_requests.c.project_id.in_(cancelled_project_ids)
            )
        )
        bind.execute(projects.delete().where(projects.c.id.in_(cancelled_project_ids)))

    bind.execute(
        projects.update().values(
            status=sa.case(
                (
                    sa.func.lower(projects.c.status).in_(
                        {"draft", "planned", "not_started", "delayed"}
                    ),
                    "not_started",
                ),
                (
                    sa.func.lower(projects.c.status).in_({"running", "suspended"}),
                    "running",
                ),
                (sa.func.lower(projects.c.status) == "completed", "completed"),
                else_="not_started",
            )
        )
    )
    op.alter_column(
        "projects",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        server_default="not_started",
    )


def downgrade() -> None:
    bind = op.get_bind()
    projects = sa.Table("projects", sa.MetaData(), autoload_with=bind)
    bind.execute(
        projects.update().values(
            status=sa.case(
                (projects.c.status == "running", "Running"),
                (projects.c.status == "completed", "Completed"),
                else_="Planned",
            )
        )
    )
    op.alter_column(
        "projects",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        server_default="Draft",
    )
