"""Add one-time project-level evaluations.

Revision ID: 20260923_0016
Revises: 20260922_0015
Create Date: 2026-09-23

Historical task evaluations are intentionally retained for audit, but new
evaluation flows write only to project_evaluations.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0016"
down_revision: str | None = "20260922_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), nullable=False),
        sa.Column("achievement_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("achievement_quality", sa.Numeric(5, 2), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", name="uq_project_evaluations_project_id"),
    )
    op.create_index(
        "ix_project_evaluations_evaluator_id",
        "project_evaluations",
        ["evaluator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_evaluations_evaluator_id", table_name="project_evaluations")
    op.drop_table("project_evaluations")
