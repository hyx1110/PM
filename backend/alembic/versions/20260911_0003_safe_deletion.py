"""Add user soft deletion support

Revision ID: 20260911_0003
Revises: 20260910_0002
Create Date: 2026-09-11
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0003"
down_revision: str | None = "20260910_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_users_is_deleted", table_name="users")
    op.drop_column("users", "is_deleted")
