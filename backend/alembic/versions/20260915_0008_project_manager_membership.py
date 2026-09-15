"""Backfill project managers as fixed project members

Revision ID: 20260915_0008
Revises: 20260914_0007
Create Date: 2026-09-15
"""

from typing import Sequence

from alembic import op

revision: str = "20260915_0008"
down_revision: str | None = "20260914_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE project_members pm
        JOIN projects p
          ON p.id = pm.project_id
         AND p.manager_id = pm.user_id
        SET pm.project_role = 'manager',
            pm.left_at = NULL,
            pm.updated_at = CURRENT_TIMESTAMP
        WHERE p.is_deleted = 0
        """
    )
    op.execute(
        """
        INSERT INTO project_members (
            project_id,
            user_id,
            project_role,
            allocation_percent,
            joined_at,
            left_at,
            created_at,
            updated_at
        )
        SELECT
            p.id,
            p.manager_id,
            'manager',
            100,
            COALESCE(p.created_at, CURRENT_TIMESTAMP),
            NULL,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM projects p
        WHERE p.is_deleted = 0
          AND NOT EXISTS (
              SELECT 1
              FROM project_members pm
              WHERE pm.project_id = p.id
                AND pm.user_id = p.manager_id
          )
        """
    )


def downgrade() -> None:
    # Data is intentionally retained: an inserted manager row cannot be safely
    # distinguished from a pre-existing legitimate membership after upgrade.
    pass
