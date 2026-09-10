from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ExecutionRecord(TimestampMixin, Base):
    __tablename__ = "execution_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    actual_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    exception_reason: Mapped[str | None] = mapped_column(Text)

