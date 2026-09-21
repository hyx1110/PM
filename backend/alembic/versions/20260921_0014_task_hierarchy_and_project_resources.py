"""Align task statuses and merge project resource requests.

Revision ID: 20260921_0014
Revises: 20260921_0013
Create Date: 2026-09-21
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

revision: str = "20260921_0014"
down_revision: str | None = "20260921_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    bind.execute(
        sa.text(
            "UPDATE tasks SET status = CASE "
            "WHEN status = 'suspended' THEN 'running' "
            "WHEN status = 'cancelled' THEN 'not_started' "
            "ELSE status END"
        )
    )
    bind.execute(
        sa.text("UPDATE execution_records SET status = 'running' WHERE status = 'paused'")
    )

    metadata = sa.MetaData()
    roles = sa.Table("roles", metadata, autoload_with=bind)
    permissions = sa.Table("permissions", metadata, autoload_with=bind)
    grants = sa.Table("role_permissions", metadata, autoload_with=bind)
    member_role_id = bind.scalar(
        sa.select(roles.c.id).where(roles.c.code == "project_member")
    )
    schedule_edit_id = bind.scalar(
        sa.select(permissions.c.id).where(permissions.c.code == "schedule:edit")
    )
    if member_role_id is not None and schedule_edit_id is not None:
        exists = bind.scalar(
            sa.select(grants.c.id).where(
                grants.c.role_id == member_role_id,
                grants.c.permission_id == schedule_edit_id,
            )
        )
        if exists is None:
            bind.execute(
                grants.insert().values(
                    role_id=member_role_id,
                    permission_id=schedule_edit_id,
                )
            )

    tables = _table_names(inspector)
    if "project_hour_requests" in tables and "project_resource_requests" not in tables:
        op.rename_table("project_hour_requests", "project_resource_requests")

    inspector = sa.inspect(bind)
    resource_columns = _column_names(inspector, "project_resource_requests")
    if "add_member_ids" not in resource_columns:
        op.add_column(
            "project_resource_requests",
            sa.Column("add_member_ids", sa.JSON(), nullable=True),
        )
    inspector = sa.inspect(bind)
    resource_columns = _column_names(inspector, "project_resource_requests")
    if "remove_member_ids" not in resource_columns:
        op.add_column(
            "project_resource_requests",
            sa.Column("remove_member_ids", sa.JSON(), nullable=True),
        )

    resource_requests = sa.Table(
        "project_resource_requests", metadata, autoload_with=bind
    )
    bind.execute(
        resource_requests.update()
        .where(resource_requests.c.add_member_ids.is_(None))
        .values(add_member_ids=[])
    )
    bind.execute(
        resource_requests.update()
        .where(resource_requests.c.remove_member_ids.is_(None))
        .values(remove_member_ids=[])
    )
    op.alter_column(
        "project_resource_requests", "add_member_ids", existing_type=sa.JSON(), nullable=False
    )
    op.alter_column(
        "project_resource_requests", "remove_member_ids", existing_type=sa.JSON(), nullable=False
    )

    inspector = sa.inspect(bind)
    if "allocation_percent" in _column_names(inspector, "project_members"):
        op.drop_column("project_members", "allocation_percent")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "allocation_percent" not in _column_names(inspector, "project_members"):
        op.add_column(
            "project_members",
            sa.Column(
                "allocation_percent",
                sa.Numeric(5, 2),
                nullable=False,
                server_default="100",
            ),
        )

    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "project_resource_requests")
    if "remove_member_ids" in columns:
        op.drop_column("project_resource_requests", "remove_member_ids")
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "project_resource_requests")
    if "add_member_ids" in columns:
        op.drop_column("project_resource_requests", "add_member_ids")
    inspector = sa.inspect(bind)
    if "project_resource_requests" in _table_names(inspector):
        op.rename_table("project_resource_requests", "project_hour_requests")
