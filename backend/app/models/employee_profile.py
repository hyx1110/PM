from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class EmployeeProfile(TimestampMixin, Base):
    """HR attributes kept separate from authentication and RBAC data."""

    __tablename__ = "employee_profiles"
    __table_args__ = (
        CheckConstraint(
            "hr_management_level IN "
            "('employee', 'department_manager', 'management_manager')",
            name="ck_employee_profiles_hr_management_level",
        ),
        CheckConstraint(
            "data_source IN ('local', 'hrdb')",
            name="ck_employee_profiles_data_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    position_id: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True
    )
    employee_type: Mapped[str | None] = mapped_column(String(1))
    local_f_name: Mapped[str | None] = mapped_column(String(60))
    english_f_name: Mapped[str | None] = mapped_column(String(60))
    local_g_name: Mapped[str | None] = mapped_column(String(60))
    english_g_name: Mapped[str | None] = mapped_column(String(60))
    preferred_name: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(1))
    job_id: Mapped[str | None] = mapped_column(String(60))
    job_title: Mapped[str | None] = mapped_column(String(60))
    eng_job_title: Mapped[str | None] = mapped_column(String(60))
    chi_job_title: Mapped[str | None] = mapped_column(String(60))
    degree: Mapped[str | None] = mapped_column(String(60))
    staff_category: Mapped[str | None] = mapped_column(String(1))
    site: Mapped[str | None] = mapped_column(String(20))
    cost_center_code: Mapped[str | None] = mapped_column(String(20))
    personnel_area: Mapped[str | None] = mapped_column(String(60))
    personnel_sub_area: Mapped[str | None] = mapped_column(String(60))
    hr_management_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="employee", index=True
    )
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
