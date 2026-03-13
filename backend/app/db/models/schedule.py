from datetime import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, SmallInteger, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.user import User
    from app.db.models.report_job import ReportJob

from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin


class Schedule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (Index("idx_schedules_active", "is_active", "next_run_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(100), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="schedules")
    user: Mapped["User"] = relationship("User", back_populates="schedules")
    report_jobs: Mapped[list["ReportJob"]] = relationship("ReportJob", back_populates="schedule")