from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class PersonalTimeBlock(TimestampMixin, Base):
    __tablename__ = "personal_time_blocks"
    __table_args__ = (
        Index(
            "ix_personal_time_user_range",
            "user_id",
            "start_time",
            "end_time",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    time_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )
    remark: Mapped[str | None] = mapped_column(Text)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
