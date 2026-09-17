"""Add multiple assignees to tasks

Revision ID: 20260916_0010
Revises: 20260916_0009
Create Date: 2026-09-16
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0010"
down_revision: str | None = "20260916_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _index_names(bind, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    return {
        item["name"]
        for item in sa.inspect(bind).get_indexes(table_name)
        if item.get("name")
    }


def upgrade() -> None:
    bind = op.get_bind()
    # MySQL DDL is non-transactional. Guard every step so an interrupted
    # migration can be resumed safely with another `alembic upgrade head`.
    if not _table_exists(bind, "task_assignees"):
        op.create_table(
            "task_assignees",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["task_id"], ["tasks.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "task_id", "user_id", name="uq_task_assignee"
            ),
        )
    indexes = _index_names(bind, "task_assignees")
    if "ix_task_assignees_task_id" not in indexes:
        op.create_index(
            "ix_task_assignees_task_id", "task_assignees", ["task_id"]
        )
    if "ix_task_assignees_user_id" not in indexes:
        op.create_index(
            "ix_task_assignees_user_id", "task_assignees", ["user_id"]
        )
    op.execute(
        "INSERT INTO task_assignees (task_id, user_id, created_at, updated_at) "
        "SELECT t.id, t.owner_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM tasks t "
        "WHERE NOT EXISTS ("
        "SELECT 1 FROM task_assignees ta "
        "WHERE ta.task_id = t.id AND ta.user_id = t.owner_id"
        ")"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "task_assignees"):
        return
    indexes = _index_names(bind, "task_assignees")
    if "ix_task_assignees_user_id" in indexes:
        op.drop_index("ix_task_assignees_user_id", table_name="task_assignees")
    if "ix_task_assignees_task_id" in indexes:
        op.drop_index("ix_task_assignees_task_id", table_name="task_assignees")
    op.drop_table("task_assignees")
