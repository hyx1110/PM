"""Remove project/task type fields and align department approval.

Revision ID: 20260921_0013
Revises: 20260918_0012
Create Date: 2026-09-21
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "20260921_0013"
down_revision: str | None = "20260918_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ix_tasks_task_type" in _index_names(inspector, "tasks"):
        op.drop_index("ix_tasks_task_type", table_name="tasks")
    inspector = sa.inspect(bind)
    if "task_type" in _column_names(inspector, "tasks"):
        op.drop_column("tasks", "task_type")
    inspector = sa.inspect(bind)
    if "project_type" in _column_names(inspector, "projects"):
        op.drop_column("projects", "project_type")

    metadata = sa.MetaData()
    roles = sa.Table("roles", metadata, autoload_with=bind)
    bind.execute(
        roles.update()
        .where(roles.c.code == "department_manager")
        .values(name="部门主管", description="部门主管系统功能角色。")
    )
    bind.execute(
        roles.update()
        .where(roles.c.code == "functional_manager")
        .values(name="职能主管", description="职能主管系统功能角色。")
    )

    # Existing pending projects are reassigned to their project department's
    # configured manager. Approved projects are deliberately left unchanged.
    projects = sa.Table("projects", metadata, autoload_with=bind)
    departments = sa.Table("departments", metadata, autoload_with=bind)
    pending_rows = bind.execute(
        sa.select(projects.c.id, departments.c.manager_id)
        .select_from(
            projects.outerjoin(
                departments,
                departments.c.id == projects.c.department_id,
            )
        )
        .where(
            projects.c.approval_status == "pending",
            projects.c.is_deleted.is_(False),
        )
    ).all()
    for project_id, manager_id in pending_rows:
        bind.execute(
            projects.update()
            .where(projects.c.id == project_id)
            .values(approver_id=manager_id)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_type" not in _column_names(inspector, "projects"):
        op.add_column(
            "projects",
            sa.Column(
                "project_type",
                sa.String(50),
                nullable=False,
                server_default="General",
            ),
        )
    inspector = sa.inspect(bind)
    if "task_type" not in _column_names(inspector, "tasks"):
        op.add_column(
            "tasks",
            sa.Column(
                "task_type",
                sa.String(30),
                nullable=False,
                server_default="Project",
            ),
        )
    inspector = sa.inspect(bind)
    if "ix_tasks_task_type" not in _index_names(inspector, "tasks"):
        op.create_index("ix_tasks_task_type", "tasks", ["task_type"])

    metadata = sa.MetaData()
    roles = sa.Table("roles", metadata, autoload_with=bind)
    bind.execute(
        roles.update()
        .where(roles.c.code == "department_manager")
        .values(name="L3", description="L3 系统功能角色。")
    )
    bind.execute(
        roles.update()
        .where(roles.c.code == "functional_manager")
        .values(name="L4", description="L4 系统功能角色。")
    )
