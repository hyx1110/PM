from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class RiskRecord(TimestampMixin, Base):
    __tablename__ = "risk_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    handling_note: Mapped[str | None] = mapped_column(Text)

