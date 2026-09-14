"""Align HR ownership, supervisor approval, task states and soft deletion

Revision ID: 20260914_0007
Revises: 20260914_0006
Create Date: 2026-09-14
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0007"
down_revision: str | None = "20260914_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("departments", "organizations"):
        op.add_column(
            table_name,
            sa.Column(
                "data_source",
                sa.String(20),
                nullable=False,
                server_default="local",
            ),
        )
        op.create_check_constraint(
            f"ck_{table_name}_data_source",
            table_name,
            "data_source IN ('local', 'hrdb')",
        )
        op.create_index(
            f"ix_{table_name}_data_source",
            table_name,
            ["data_source"],
        )

    op.add_column(
        "employee_profiles",
        sa.Column(
            "data_source",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
    )
    op.create_check_constraint(
        "ck_employee_profiles_data_source",
        "employee_profiles",
        "data_source IN ('local', 'hrdb')",
    )
    op.create_index(
        "ix_employee_profiles_data_source",
        "employee_profiles",
        ["data_source"],
    )

    op.add_column(
        "projects", sa.Column("approver_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_projects_approver_id_users",
        "projects",
        "users",
        ["approver_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_approver_id", "projects", ["approver_id"])
    op.execute(
        """
        UPDATE projects p
        LEFT JOIN users u ON u.id = p.created_by
        SET p.approver_id = u.supervisor_id
        WHERE p.approval_status = 'pending'
        """
    )

    op.add_column(
        "tasks",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index("ix_tasks_is_deleted", "tasks", ["is_deleted"])
    op.execute(
        "UPDATE tasks SET status = 'not_started' "
        "WHERE status IN ('pending', 'confirmed')"
    )
    op.execute("UPDATE tasks SET status = 'running' WHERE status = 'delayed'")

    op.add_column(
        "notifications",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_notifications_is_deleted", "notifications", ["is_deleted"]
    )

    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id, is_manual, is_hr_auto)
        SELECT u.id, r.id, 1, 0
        FROM users u
        JOIN roles r ON r.code = 'project_member'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_is_deleted", table_name="notifications")
    op.drop_column("notifications", "is_deleted")
    op.drop_index("ix_tasks_is_deleted", table_name="tasks")
    op.drop_column("tasks", "is_deleted")
    op.drop_index("ix_projects_approver_id", table_name="projects")
    op.drop_constraint(
        "fk_projects_approver_id_users", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "approver_id")
    op.drop_index(
        "ix_employee_profiles_data_source", table_name="employee_profiles"
    )
    op.drop_constraint(
        "ck_employee_profiles_data_source",
        "employee_profiles",
        type_="check",
    )
    op.drop_column("employee_profiles", "data_source")
    for table_name in ("organizations", "departments"):
        op.drop_index(
            f"ix_{table_name}_data_source", table_name=table_name
        )
        op.drop_constraint(
            f"ck_{table_name}_data_source",
            table_name,
            type_="check",
        )
        op.drop_column(table_name, "data_source")
