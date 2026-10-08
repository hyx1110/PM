"""Require department approval for newly created top-level tasks.

Revision ID: 20261008_0020
Revises: 20261008_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0020"
down_revision = "20261008_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve existing task/booking/execution history. No retroactive approvals.
    # MySQL DDL commits independently; allow retry after a partially applied upgrade.
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    columns = [
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
    ]
    for column in columns:
        if column.name not in existing_columns:
            op.add_column("tasks", column)
    existing_fks = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("tasks")}
    for name in ("created_by", "approver_id", "approved_by"):
        if (name,) not in existing_fks:
            op.create_foreign_key(f"fk_tasks_{name}", "tasks", "users", [name], ["id"], ondelete="SET NULL")
    if "ix_tasks_approval_status" not in {index["name"] for index in inspector.get_indexes("tasks")}:
        op.create_index("ix_tasks_approval_status", "tasks", ["approval_status"])
    op.execute("UPDATE tasks SET approval_status = 'not_required' WHERE parent_id IS NOT NULL AND approval_status = 'approved'")
    # Only historical rows are grandfathered. New inserts fail closed by default.
    op.alter_column("tasks", "approval_status", existing_type=sa.String(20), existing_nullable=False, server_default="pending")


def downgrade() -> None:
    op.drop_index("ix_tasks_approval_status", table_name="tasks")
    for name in ("approved_by", "approver_id", "created_by"):
        op.drop_constraint(f"fk_tasks_{name}", "tasks", type_="foreignkey")
    for name in ("approval_note", "approved_at", "approved_by", "submitted_at", "approver_id", "created_by", "approval_status"):
        op.drop_column("tasks", name)
