from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.schedule import Schedule
    from app.db.models.report_job import ReportJob
    from app.db.models.dead_letter import DeadLetterQueue


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="tenant"
    )
    report_jobs: Mapped[list["ReportJob"]] = relationship(
        "ReportJob", back_populates="tenant"
    )
    dlq_entries: Mapped[list["DeadLetterQueue"]] = relationship(
        "DeadLetterQueue", back_populates="tenant"
    )
