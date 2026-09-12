"""Project approval, hour quota, and work calendar

Revision ID: 20260911_0004
Revises: 20260911_0003
Create Date: 2026-09-11
"""

from datetime import date
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0004"
down_revision: str | None = "20260911_0003"
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
    op.execute("UPDATE roles SET name = 'L3' WHERE code = 'department_manager'")
    op.execute("UPDATE roles SET name = 'L4' WHERE code = 'functional_manager'")
    op.execute(
        """
        INSERT INTO permissions (code, name, module)
        SELECT 'calendar:manage', '维护工作日历', 'schedule'
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'calendar:manage')
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r
        JOIN permissions p ON p.code = 'calendar:manage'
        WHERE r.code IN ('super_admin', 'department_manager')
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )
    op.add_column(
        "projects",
        sa.Column("budget_hours", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "projects",
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="approved"),
    )
    op.add_column("projects", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("approval_note", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_projects_created_by",
        "projects",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_projects_approved_by",
        "projects",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_created_by", "projects", ["created_by"])
    op.create_index("ix_projects_approved_by", "projects", ["approved_by"])
    op.create_index("ix_projects_approval_status", "projects", ["approval_status"])

    # Existing projects are treated as approved. Their initial quota is the
    # larger of task estimates and already reserved schedule hours.
    op.execute(
        """
        UPDATE projects p
        SET p.budget_hours = GREATEST(
            COALESCE((SELECT SUM(t.estimated_hours) FROM tasks t WHERE t.project_id = p.id), 0),
            COALESCE((SELECT SUM(s.planned_hours) FROM schedule_bookings s
                      WHERE s.project_id = p.id
                        AND s.status IN ('pending','confirmed','changed','running','completed')), 0)
        )
        """
    )
    op.alter_column(
        "projects",
        "approval_status",
        existing_type=sa.String(20),
        server_default="pending",
        existing_nullable=False,
    )
    op.alter_column(
        "schedule_bookings",
        "status",
        existing_type=sa.String(30),
        server_default="pending",
        existing_nullable=False,
    )

    op.create_table(
        "project_hour_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requested_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_project_hour_requests_project_id", "project_hour_requests", ["project_id"])
    op.create_index("ix_project_hour_requests_status", "project_hour_requests", ["status"])
    op.create_index("ix_project_hour_requests_requested_by", "project_hour_requests", ["requested_by"])

    calendar = op.create_table(
        "work_calendar_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("work_date", name="uq_work_calendar_days_work_date"),
    )
    op.create_index("ix_work_calendar_days_work_date", "work_calendar_days", ["work_date"])
    op.create_index("ix_work_calendar_days_day_type", "work_calendar_days", ["day_type"])

    source = "国务院办公厅关于2026年部分节假日安排的通知（国办发明电〔2025〕7号）"
    holiday_ranges = [
        ("元旦", date(2026, 1, 1), date(2026, 1, 3)),
        ("春节", date(2026, 2, 15), date(2026, 2, 23)),
        ("清明节", date(2026, 4, 4), date(2026, 4, 6)),
        ("劳动节", date(2026, 5, 1), date(2026, 5, 5)),
        ("端午节", date(2026, 6, 19), date(2026, 6, 21)),
        ("中秋节", date(2026, 9, 25), date(2026, 9, 27)),
        ("国庆节", date(2026, 10, 1), date(2026, 10, 7)),
    ]
    rows: list[dict] = []
    for name, start, end in holiday_ranges:
        current = start
        while current <= end:
            rows.append({"work_date": current, "day_type": "holiday", "name": name, "source": source})
            current = date.fromordinal(current.toordinal() + 1)
    for work_date in (
        date(2026, 1, 4),
        date(2026, 2, 14),
        date(2026, 2, 28),
        date(2026, 5, 9),
        date(2026, 9, 20),
        date(2026, 10, 10),
    ):
        rows.append({"work_date": work_date, "day_type": "workday", "name": "法定调休工作日", "source": source})
    op.bulk_insert(calendar, rows)


def downgrade() -> None:
    op.alter_column(
        "schedule_bookings",
        "status",
        existing_type=sa.String(30),
        server_default="draft",
        existing_nullable=False,
    )
    op.drop_table("work_calendar_days")
    op.drop_table("project_hour_requests")
    op.drop_index("ix_projects_approval_status", table_name="projects")
    op.drop_index("ix_projects_approved_by", table_name="projects")
    op.drop_index("ix_projects_created_by", table_name="projects")
    op.drop_constraint("fk_projects_approved_by", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_created_by", "projects", type_="foreignkey")
    for column in (
        "approval_note",
        "approved_at",
        "approved_by",
        "created_by",
        "approval_status",
        "budget_hours",
    ):
        op.drop_column("projects", column)
    op.execute("UPDATE roles SET name = '部门主管' WHERE code = 'department_manager'")
    op.execute("UPDATE roles SET name = '职能主管' WHERE code = 'functional_manager'")
    op.execute(
        """
        DELETE rp FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE p.code = 'calendar:manage'
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'calendar:manage'")
