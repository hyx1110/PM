"""Overtime requests, linked execution records and email delivery state.

Revision ID: 20260928_0017
Revises: 20260923_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260928_0017"
down_revision = "20260923_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "overtime_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("review_note", sa.Text()),
        sa.Column("withdrawn_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        sa.CheckConstraint("end_time > start_time", name="ck_overtime_time_order"),
        sa.CheckConstraint("hours > 0", name="ck_overtime_hours_positive"),
    )
    op.create_index("ix_overtime_requests_project_id", "overtime_requests", ["project_id"])
    op.create_index("ix_overtime_requests_task_id", "overtime_requests", ["task_id"])
    op.create_index("ix_overtime_user_status_time", "overtime_requests", ["user_id", "status", "start_time"])
    op.create_index("ix_overtime_approver_status", "overtime_requests", ["approver_id", "status"])
    op.add_column("execution_records", sa.Column("overtime_request_id", sa.Integer(), nullable=True))
    op.create_index("ix_execution_records_overtime_request_id", "execution_records", ["overtime_request_id"])
    op.create_foreign_key("fk_execution_overtime_request", "execution_records", "overtime_requests", ["overtime_request_id"], ["id"], ondelete="RESTRICT")
    # Existing notifications are deliberately not queued for a historical mass mailing.
    op.add_column("notifications", sa.Column("email_status", sa.String(20), nullable=False, server_default="skipped"))
    op.add_column("notifications", sa.Column("email_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("notifications", sa.Column("email_last_error", sa.String(255)))
    op.add_column("notifications", sa.Column("email_next_attempt_at", sa.DateTime()))
    op.create_index("ix_notifications_email_status", "notifications", ["email_status"])
    op.create_index("ix_notifications_email_next_attempt_at", "notifications", ["email_next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_email_next_attempt_at", table_name="notifications")
    op.drop_index("ix_notifications_email_status", table_name="notifications")
    for column in ("email_next_attempt_at", "email_last_error", "email_attempts", "email_status"):
        op.drop_column("notifications", column)
    op.drop_constraint("fk_execution_overtime_request", "execution_records", type_="foreignkey")
    op.drop_index("ix_execution_records_overtime_request_id", table_name="execution_records")
    op.drop_column("execution_records", "overtime_request_id")
    op.drop_table("overtime_requests")
