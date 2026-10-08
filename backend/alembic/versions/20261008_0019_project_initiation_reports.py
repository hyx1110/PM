"""Store project initiation report metadata; files remain on private server storage.

Revision ID: 20261008_0019
Revises: 20260929_0018
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0019"
down_revision = "20260929_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_initiation_reports",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_name", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    # Intentionally retain server files; downgrade only removes their DB metadata.
    op.drop_table("project_initiation_reports")
