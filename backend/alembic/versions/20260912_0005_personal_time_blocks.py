"""Add personal time blocks

Revision ID: 20260912_0005
Revises: 20260911_0004
Create Date: 2026-09-12
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0005"
down_revision: str | None = "20260911_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_time_blocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("time_type", sa.String(30), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("planned_hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_personal_time_blocks_user_id", "personal_time_blocks", ["user_id"]
    )
    op.create_index(
        "ix_personal_time_blocks_time_type", "personal_time_blocks", ["time_type"]
    )
    op.create_index(
        "ix_personal_time_blocks_status", "personal_time_blocks", ["status"]
    )
    op.create_index(
        "ix_personal_time_user_range",
        "personal_time_blocks",
        ["user_id", "start_time", "end_time", "status"],
    )


def downgrade() -> None:
    op.drop_table("personal_time_blocks")
