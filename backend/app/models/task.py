from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    planned_start: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_started", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    description: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(
        nullable=False, default=False, index=True
    )


class TaskAssignee(TimestampMixin, Base):
    __tablename__ = "task_assignees"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
