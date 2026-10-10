"""Allow resource requests to change both project plan dates.

Revision ID: 20261009_0021
Revises: 20261008_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0021"
down_revision = "20261008_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL DDL is not transactional; allow retry after a partial upgrade.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("project_resource_requests")}
    for name in ("original_planned_start", "requested_planned_start"):
        if name not in columns:
            op.add_column("project_resource_requests", sa.Column(name, sa.Date(), nullable=True))
    # Do not invent historical start-date snapshots for old end-only requests.


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("project_resource_requests")}
    for name in ("requested_planned_start", "original_planned_start"):
        if name in columns:
            op.drop_column("project_resource_requests", name)
