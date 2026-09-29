"""Add approval-controlled project end-date extensions to resource requests.

Revision ID: 20260929_0018
Revises: 20260928_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0018"
down_revision = "20260928_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing requests remain valid hours/member-only changes; no data rewrite.
    # MySQL DDL is not transactional: allow a retry after a partial upgrade.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("project_resource_requests")}
    for name in ("original_planned_end", "requested_planned_end"):
        if name not in columns:
            op.add_column("project_resource_requests", sa.Column(name, sa.Date(), nullable=True))


def downgrade() -> None:
    # Downgrade discards extension history, but does not undo approved project dates.
    op.drop_column("project_resource_requests", "requested_planned_end")
    op.drop_column("project_resource_requests", "original_planned_end")
