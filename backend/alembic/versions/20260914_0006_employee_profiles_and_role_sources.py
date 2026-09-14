"""Add employee profiles and separate manual/HR role sources

Revision ID: 20260914_0006
Revises: 20260912_0005
Create Date: 2026-09-14
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0006"
down_revision: str | None = "20260912_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(30),
        type_=sa.String(60),
        existing_nullable=True,
    )
    op.add_column("users", sa.Column("employee_no", sa.String(50), nullable=True))
    op.execute("UPDATE users SET employee_no = username WHERE employee_no IS NULL")
    op.alter_column(
        "users",
        "employee_no",
        existing_type=sa.String(50),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_users_employee_no", "users", ["employee_no"]
    )
    op.create_index("ix_users_employee_no", "users", ["employee_no"])
    op.create_check_constraint(
        "ck_users_employee_no_username",
        "users",
        "employee_no = username",
    )

    op.add_column(
        "user_roles",
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "user_roles",
        sa.Column("is_hr_auto", sa.Boolean(), nullable=False, server_default=sa.text("0")),
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
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "hr_management_level IN "
            "('employee', 'department_manager', 'management_manager')",
            name="ck_employee_profiles_hr_management_level",
        ),
        sa.UniqueConstraint("user_id", name="uq_employee_profiles_user_id"),
        sa.UniqueConstraint("position_id", name="uq_employee_profiles_position_id"),
    )
    op.create_index(
        "ix_employee_profiles_user_id", "employee_profiles", ["user_id"]
    )
    op.create_index(
        "ix_employee_profiles_position_id", "employee_profiles", ["position_id"]
    )
    op.create_index(
        "ix_employee_profiles_hr_management_level",
        "employee_profiles",
        ["hr_management_level"],
    )
    op.execute(
        """
        INSERT INTO employee_profiles (user_id, hr_management_level)
        SELECT id, 'employee' FROM users
        """
    )


def downgrade() -> None:
    op.drop_table("employee_profiles")
    op.drop_constraint(
        "ck_user_roles_has_source", "user_roles", type_="check"
    )
    op.drop_column("user_roles", "is_hr_auto")
    op.drop_column("user_roles", "is_manual")
    op.drop_constraint(
        "ck_users_employee_no_username", "users", type_="check"
    )
    op.drop_index("ix_users_employee_no", table_name="users")
    op.drop_constraint("uq_users_employee_no", "users", type_="unique")
    op.drop_column("users", "employee_no")
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(60),
        type_=sa.String(30),
        existing_nullable=True,
    )
