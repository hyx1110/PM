"""V2.0 risk, notifications, import jobs and board history

Revision ID: 20260910_0002
Revises: 20260909_0001
Create Date: 2026-09-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0002"
down_revision: str | None = "20260909_0001"
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
    op.add_column("schedule_bookings", sa.Column("source_booking_id", sa.Integer(), nullable=True))
    op.add_column("schedule_bookings", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_foreign_key(
        "fk_schedule_bookings_source_booking_id",
        "schedule_bookings",
        "schedule_bookings",
        ["source_booking_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_schedule_bookings_source_booking_id", "schedule_bookings", ["source_booking_id"])

    op.add_column("risk_records", sa.Column("fingerprint", sa.String(120), nullable=True))
    op.add_column("risk_records", sa.Column("title", sa.String(200), nullable=True))
    op.add_column("risk_records", sa.Column("source_data", sa.JSON(), nullable=True))
    op.add_column(
        "risk_records",
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.add_column("risk_records", sa.Column("due_at", sa.DateTime(), nullable=True))
    op.add_column("risk_records", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.create_index("ix_risk_records_fingerprint", "risk_records", ["fingerprint"], unique=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("related_type", sa.String(50), nullable=True),
        sa.Column("related_id", sa.String(64), nullable=True),
        sa.Column("delivered_channels", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unread"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
    )
    for name, columns in {
        "ix_notifications_recipient_id": ["recipient_id"],
        "ix_notifications_event_type": ["event_type"],
        "ix_notifications_related_id": ["related_id"],
        "ix_notifications_status": ["status"],
    }.items():
        op.create_index(name, "notifications", columns)

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("wecom_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("dingtalk_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("upcoming_hours", sa.Integer(), nullable=False, server_default="24"),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="RESTRICT"),
    )
    for name, columns in {
        "ix_import_jobs_resource_type": ["resource_type"],
        "ix_import_jobs_status": ["status"],
        "ix_import_jobs_operator_id": ["operator_id"],
    }.items():
        op.create_index(name, "import_jobs", columns)


def downgrade() -> None:
    op.drop_table("import_jobs")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_index("ix_risk_records_fingerprint", table_name="risk_records")
    for column in ("resolved_at", "due_at", "detected_at", "source_data", "title", "fingerprint"):
        op.drop_column("risk_records", column)
    op.drop_index("ix_schedule_bookings_source_booking_id", table_name="schedule_bookings")
    op.drop_constraint("fk_schedule_bookings_source_booking_id", "schedule_bookings", type_="foreignkey")
    op.drop_column("schedule_bookings", "version")
    op.drop_column("schedule_bookings", "source_booking_id")
