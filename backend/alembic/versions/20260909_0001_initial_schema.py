"""V1.0 initial schema

Revision ID: 20260909_0001
Revises:
Create Date: 2026-09-09
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_departments_code"),
    )
    op.create_index("ix_departments_status", "departments", ["status"])

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *timestamps(),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("department_id", "code", name="uq_organization_department_code"),
    )
    op.create_index("ix_organizations_department_id", "organizations", ["department_id"])
    op.create_index("ix_organizations_parent_id", "organizations", ["parent_id"])
    op.create_index("ix_organizations_status", "organizations", ["status"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *timestamps(),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supervisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_name", "users", ["name"])
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_supervisor_id", "users", ["supervisor_id"])
    op.create_index("ix_users_status", "users", ["status"])
    op.create_foreign_key("fk_departments_manager_id_users", "departments", "users", ["manager_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_organizations_manager_id_users", "organizations", "users", ["manager_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("project_type", sa.String(50), nullable=False, server_default="General"),
        sa.Column("manager_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="Draft"),
        sa.Column("planned_start", sa.Date(), nullable=False),
        sa.Column("planned_end", sa.Date(), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *timestamps(),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("code", name="uq_projects_code"),
    )
    for name, columns in {
        "ix_projects_code": ["code"],
        "ix_projects_name": ["name"],
        "ix_projects_manager_id": ["manager_id"],
        "ix_projects_department_id": ["department_id"],
        "ix_projects_status": ["status"],
        "ix_projects_is_deleted": ["is_deleted"],
    }.items():
        op.create_index(name, "projects", columns)

    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("allocation_percent", sa.Numeric(5, 2), nullable=False, server_default="100"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("task_type", sa.String(30), nullable=False, server_default="Project"),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("planned_start", sa.DateTime(), nullable=False),
        sa.Column("planned_end", sa.DateTime(), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="not_started"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
    )
    for name, columns in {
        "ix_tasks_project_id": ["project_id"],
        "ix_tasks_parent_id": ["parent_id"],
        "ix_tasks_name": ["name"],
        "ix_tasks_task_type": ["task_type"],
        "ix_tasks_owner_id": ["owner_id"],
        "ix_tasks_planned_end": ["planned_end"],
        "ix_tasks_status": ["status"],
    }.items():
        op.create_index(name, "tasks", columns)

    op.create_table(
        "schedule_bookings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("planned_hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_schedule_bookings_user_id", "schedule_bookings", ["user_id"])
    op.create_index("ix_schedule_bookings_project_id", "schedule_bookings", ["project_id"])
    op.create_index("ix_schedule_bookings_task_id", "schedule_bookings", ["task_id"])
    op.create_index("ix_schedule_bookings_status", "schedule_bookings", ["status"])
    op.create_index("ix_schedule_user_range", "schedule_bookings", ["user_id", "start_time", "end_time", "status"])
    op.create_index("ix_schedule_project_range", "schedule_bookings", ["project_id", "start_time", "end_time"])

    op.create_table(
        "execution_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actual_start", sa.DateTime(), nullable=False),
        sa.Column("actual_end", sa.DateTime(), nullable=True),
        sa.Column("actual_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("exception_reason", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_execution_records_task_id", "execution_records", ["task_id"])
    op.create_index("ix_execution_records_user_id", "execution_records", ["user_id"])
    op.create_index("ix_execution_records_actual_start", "execution_records", ["actual_start"])
    op.create_index("ix_execution_records_status", "execution_records", ["status"])

    op.create_table(
        "task_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), nullable=False),
        sa.Column("achievement_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("achievement_quality", sa.Numeric(5, 2), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("task_id", name="uq_task_evaluations_task_id"),
    )

    op.create_table(
        "risk_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("risk_type", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("handled_by", sa.Integer(), nullable=True),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("handling_note", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handled_by"], ["users.id"], ondelete="SET NULL"),
    )
    for name, columns in {
        "ix_risk_records_risk_type": ["risk_type"],
        "ix_risk_records_project_id": ["project_id"],
        "ix_risk_records_task_id": ["task_id"],
        "ix_risk_records_user_id": ["user_id"],
        "ix_risk_records_status": ["status"],
    }.items():
        op.create_index(name, "risk_records", columns)

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("object_type", sa.String(50), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="SET NULL"),
    )
    for name, columns in {
        "ix_operation_logs_operator_id": ["operator_id"],
        "ix_operation_logs_module": ["module"],
        "ix_operation_logs_action": ["action"],
        "ix_operation_logs_object_id": ["object_id"],
        "ix_operation_logs_created_at": ["created_at"],
    }.items():
        op.create_index(name, "operation_logs", columns)


def downgrade() -> None:
    op.drop_table("operation_logs")
    op.drop_table("risk_records")
    op.drop_table("task_evaluations")
    op.drop_table("execution_records")
    op.drop_table("schedule_bookings")
    op.drop_table("tasks")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_constraint("fk_organizations_manager_id_users", "organizations", type_="foreignkey")
    op.drop_constraint("fk_departments_manager_id_users", "departments", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("departments")

