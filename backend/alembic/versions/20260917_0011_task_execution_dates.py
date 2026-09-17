"""Store task and execution periods as calendar dates.

Revision ID: 20260917_0011
Revises: 20260916_0010
Create Date: 2026-09-17

Existing DATETIME values are intentionally converted with DATE(...), because
the corresponding business fields no longer carry an hour/minute component.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0011"
down_revision: str | None = "20260916_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_type(bind, table_name: str, column_name: str):
    for column in sa.inspect(bind).get_columns(table_name):
        if column["name"] == column_name:
            return column["type"]
    return None


def _to_date(bind, table_name: str, column_name: str, nullable: bool) -> None:
    current_type = _column_type(bind, table_name, column_name)
    if current_type is None or isinstance(current_type, sa.Date) and not isinstance(current_type, sa.DateTime):
        return
    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = DATE({column_name}) "
            f"WHERE {column_name} IS NOT NULL"
        )
    )
    op.alter_column(
        table_name,
        column_name,
        existing_type=current_type,
        type_=sa.Date(),
        existing_nullable=nullable,
    )


def _to_datetime(bind, table_name: str, column_name: str, nullable: bool) -> None:
    current_type = _column_type(bind, table_name, column_name)
    if current_type is None or isinstance(current_type, sa.DateTime):
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=current_type,
        type_=sa.DateTime(),
        existing_nullable=nullable,
    )


def upgrade() -> None:
    bind = op.get_bind()
    _to_date(bind, "tasks", "planned_start", False)
    _to_date(bind, "tasks", "planned_end", False)
    _to_date(bind, "execution_records", "actual_start", False)
    _to_date(bind, "execution_records", "actual_end", True)


def downgrade() -> None:
    bind = op.get_bind()
    _to_datetime(bind, "execution_records", "actual_end", True)
    _to_datetime(bind, "execution_records", "actual_start", False)
    _to_datetime(bind, "tasks", "planned_end", False)
    _to_datetime(bind, "tasks", "planned_start", False)
