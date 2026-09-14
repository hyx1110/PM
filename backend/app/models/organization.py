from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Department(TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint(
            "data_source IN ('local', 'hrdb')",
            name="ck_departments_data_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "code", name="uq_organization_department_code"
        ),
        CheckConstraint(
            "data_source IN ('local', 'hrdb')",
            name="ck_organizations_data_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )
