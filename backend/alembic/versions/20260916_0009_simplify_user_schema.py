"""Simplify users to accounts, organization relations and system roles

Revision ID: 20260916_0009
Revises: 20260915_0008
Create Date: 2026-09-16
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0009"
down_revision: str | None = "20260915_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    return {
        column["name"] for column in sa.inspect(bind).get_columns(table_name)
    }


def _drop_check_if_supported(bind, table_name: str, constraint_name: str) -> None:
    """Drop a persisted CHECK without breaking older MySQL releases."""
    if not _table_exists(bind, table_name):
        return
    check_names = {
        constraint.get("name")
        for constraint in sa.inspect(bind).get_check_constraints(table_name)
        if constraint.get("name")
    }
    if constraint_name not in check_names:
        return

    version_text = str(bind.exec_driver_sql("SELECT VERSION()").scalar() or "")
    if "mariadb" in version_text.lower():
        bind.exec_driver_sql(
            f"ALTER TABLE `{table_name}` DROP CONSTRAINT `{constraint_name}`"
        )
        return

    version = tuple(getattr(bind.dialect, "server_version_info", ()) or ())
    if version >= (8, 0, 16):
        op.drop_constraint(constraint_name, table_name, type_="check")


def _drop_index_if_present(bind, table_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    index_names = {
        index.get("name")
        for index in sa.inspect(bind).get_indexes(table_name)
        if index.get("name")
    }
    if index_name in index_names:
        op.drop_index(index_name, table_name=table_name)


def _drop_unique_if_present(bind, table_name: str, constraint_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    unique_names = {
        constraint.get("name")
        for constraint in sa.inspect(bind).get_unique_constraints(table_name)
        if constraint.get("name")
    }
    if constraint_name in unique_names:
        op.drop_constraint(constraint_name, table_name, type_="unique")


def upgrade() -> None:
    bind = op.get_bind()

    # The former HR profile and role-source model is intentionally removed.
    # Its data cannot be represented by the simplified user model. Every step
    # is guarded because MySQL DDL is non-transactional: a failed attempt may
    # already have applied one or more preceding statements.
    if _table_exists(bind, "employee_profiles"):
        op.drop_table("employee_profiles")

    _drop_check_if_supported(bind, "user_roles", "ck_user_roles_has_source")
    if "is_hr_auto" in _column_names(bind, "user_roles"):
        op.drop_column("user_roles", "is_hr_auto")
    if "is_manual" in _column_names(bind, "user_roles"):
        op.drop_column("user_roles", "is_manual")

    _drop_check_if_supported(bind, "users", "ck_users_employee_no_username")
    _drop_index_if_present(bind, "users", "ix_users_username")
    _drop_unique_if_present(bind, "users", "uq_users_username")
    if "username" in _column_names(bind, "users"):
        op.drop_column("users", "username")
    if "phone" in _column_names(bind, "users"):
        op.drop_column("users", "phone")


def downgrade() -> None:
    # Recreate the old schema for rollback. Removed HR profile values cannot be
    # restored, so each user receives a minimal local employee profile.
    op.add_column("users", sa.Column("phone", sa.String(60), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(50), nullable=True))
    op.execute("UPDATE users SET username = employee_no")
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_check_constraint(
        "ck_users_employee_no_username",
        "users",
        "employee_no = username",
    )

    op.add_column(
        "user_roles",
        sa.Column(
            "is_manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "user_roles",
        sa.Column(
            "is_hr_auto",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_user_roles_has_source",
        "user_roles",
        "is_manual = 1 OR is_hr_auto = 1",
    )

    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.String(20), nullable=True),
        sa.Column("employee_type", sa.String(1), nullable=True),
        sa.Column("local_f_name", sa.String(60), nullable=True),
        sa.Column("english_f_name", sa.String(60), nullable=True),
        sa.Column("local_g_name", sa.String(60), nullable=True),
        sa.Column("english_g_name", sa.String(60), nullable=True),
        sa.Column("preferred_name", sa.String(100), nullable=True),
        sa.Column("gender", sa.String(1), nullable=True),
        sa.Column("job_id", sa.String(60), nullable=True),
        sa.Column("job_title", sa.String(60), nullable=True),
        sa.Column("eng_job_title", sa.String(60), nullable=True),
        sa.Column("chi_job_title", sa.String(60), nullable=True),
        sa.Column("degree", sa.String(60), nullable=True),
        sa.Column("staff_category", sa.String(1), nullable=True),
        sa.Column("site", sa.String(20), nullable=True),
        sa.Column("cost_center_code", sa.String(20), nullable=True),
        sa.Column("personnel_area", sa.String(60), nullable=True),
        sa.Column("personnel_sub_area", sa.String(60), nullable=True),
        sa.Column(
            "hr_management_level",
            sa.String(30),
            nullable=False,
            server_default="employee",
        ),
        sa.Column(
            "data_source",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "hr_management_level IN "
            "('employee', 'department_manager', 'management_manager')",
            name="ck_employee_profiles_hr_management_level",
        ),
        sa.CheckConstraint(
            "data_source IN ('local', 'hrdb')",
            name="ck_employee_profiles_data_source",
        ),
        sa.UniqueConstraint("user_id", name="uq_employee_profiles_user_id"),
        sa.UniqueConstraint(
            "position_id", name="uq_employee_profiles_position_id"
        ),
    )
    op.create_index(
        "ix_employee_profiles_user_id", "employee_profiles", ["user_id"]
    )
    op.create_index(
        "ix_employee_profiles_position_id",
        "employee_profiles",
        ["position_id"],
    )
    op.create_index(
        "ix_employee_profiles_hr_management_level",
        "employee_profiles",
        ["hr_management_level"],
    )
    op.create_index(
        "ix_employee_profiles_data_source",
        "employee_profiles",
        ["data_source"],
    )
    op.execute(
        "INSERT INTO employee_profiles "
        "(user_id, hr_management_level, data_source) "
        "SELECT id, 'employee', 'local' FROM users"
    )
