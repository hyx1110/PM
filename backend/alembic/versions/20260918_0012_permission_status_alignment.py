"""Align existing role grants and task states with the September bug fixes.

Revision ID: 20260918_0012
Revises: 20260917_0011

Adds only required grants, preserving customized role permissions. Repairs open
project tasks using their newest non-deleted execution, without reopening closed
or evaluated projects. No application imports or service startup are required.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0012"
down_revision: str | None = "20260917_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    roles = sa.Table("roles", metadata, autoload_with=bind)
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    grants = sa.Table("role_permissions", metadata, autoload_with=bind)
    additions = {
        "department_manager": {"evaluation:edit"},
        "functional_manager": {"project:edit", "schedule:edit", "evaluation:edit"},
    }
    for role_code, permission_codes in additions.items():
        role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.code == role_code))
        if role_id is None:
            continue  # Fresh databases receive all grants from init_data.
        for code in permission_codes:
            permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.code == code))
            if permission_id is None:
                continue
            exists = bind.scalar(sa.select(grants.c.id).where(
                grants.c.role_id == role_id, grants.c.permission_id == permission_id,
            ))
            if exists is None:
                bind.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))

    # Ordinary project members are read-only at project level. Remove the
    # temporary grant used by an earlier implementation of this permission fix.
    member_role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.code == "project_member"))
    project_edit_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.code == "project:edit"))
    if member_role_id is not None and project_edit_id is not None:
        bind.execute(grants.delete().where(
            grants.c.role_id == member_role_id,
            grants.c.permission_id == project_edit_id,
        ))

    tasks = sa.Table("tasks", metadata, autoload_with=bind)
    projects = sa.Table("projects", metadata, autoload_with=bind)
    records = sa.Table("execution_records", metadata, autoload_with=bind)
    evaluations = sa.Table("task_evaluations", metadata, autoload_with=bind)
    evaluated_projects = sa.select(tasks.c.project_id).join(evaluations, evaluations.c.task_id == tasks.c.id)
    rows = bind.execute(sa.select(tasks.c.id, tasks.c.project_id, tasks.c.parent_id, tasks.c.status)
        .join(projects, projects.c.id == tasks.c.project_id)
        .where(tasks.c.is_deleted.is_(False), projects.c.is_deleted.is_(False),
               projects.c.status.notin_({"Completed", "Cancelled"}),
               projects.c.id.notin_(evaluated_projects))).mappings().all()
    state = {row["id"]: row["status"] for row in rows}
    children: dict[int, list[int]] = {}
    for row in rows:
        if row["parent_id"] is not None:
            children.setdefault(row["parent_id"], []).append(row["id"])

    latest_status: dict[int, str] = {}
    if state:
        ordered = bind.execute(sa.select(records.c.task_id, records.c.status)
            .where(records.c.task_id.in_(state), records.c.is_deleted.is_(False))
            .order_by(records.c.created_at.desc(), records.c.id.desc()))
        for task_id, status in ordered:
            latest_status.setdefault(task_id, status)
    for task_id in state:
        if task_id in children or state[task_id] == "cancelled":
            continue
        state[task_id] = {"completed": "completed", "paused": "suspended", "running": "running"}.get(latest_status.get(task_id), "not_started")
    # Parents are currently two-level; bounded passes also handle deeper legacy
    # trees without depending on row ordering or risking an infinite loop.
    for _ in range(len(children) + 1):
        changed = False
        for parent_id, child_ids in children.items():
            if parent_id not in state or state[parent_id] == "cancelled":
                continue
            statuses = [state[item] for item in child_ids if state[item] != "cancelled"]
            value = (
                "completed" if statuses and all(item == "completed" for item in statuses) else
                "running" if "running" in statuses else
                "suspended" if "suspended" in statuses else
                "running" if "completed" in statuses else "not_started"
            )
            if state[parent_id] != value:
                state[parent_id] = value
                changed = True
        if not changed:
            break
    for row in rows:
        if state[row["id"]] != row["status"]:
            bind.execute(tasks.update().where(tasks.c.id == row["id"]).values(status=state[row["id"]]))

    # Keep open approved projects aligned without ever auto-completing them.
    project_task_states: dict[int, list[str]] = {}
    for row in rows:
        if state[row["id"]] != "cancelled":
            project_task_states.setdefault(row["project_id"], []).append(state[row["id"]])
    for project_id, statuses in project_task_states.items():
        project_row = bind.execute(sa.select(
            projects.c.approval_status, projects.c.status,
        ).where(projects.c.id == project_id)).mappings().first()
        if not project_row or project_row["approval_status"] != "approved":
            continue
        desired = (
            "Running" if any(value in {"running", "completed"} for value in statuses) else
            "Suspended" if "suspended" in statuses else "Planned"
        )
        actual_start = bind.scalar(sa.select(sa.func.min(records.c.actual_start))
            .select_from(records.join(tasks, tasks.c.id == records.c.task_id))
            .where(tasks.c.project_id == project_id, tasks.c.is_deleted.is_(False),
                   records.c.is_deleted.is_(False)))
        bind.execute(projects.update().where(projects.c.id == project_id).values(
            status=desired, actual_start=actual_start, actual_end=None,
        ))


def downgrade() -> None:
    # Do not revoke grants that may have existed before this migration or
    # restore stale task states. Restore a pre-upgrade backup for data rollback.
    pass
