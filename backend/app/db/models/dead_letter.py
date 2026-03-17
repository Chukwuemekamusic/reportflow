from sqlalchemy import Boolean, SmallInteger, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.report_job import ReportJob
from app.db.base import Base
from app.db.models.mixins import UUIDMixin


class DeadLetterQueue(UUIDMixin, Base):
    """
    Dead Letter Queue for failed jobs after max retries exhausted.
    Stores full error trace for debugging and allows admin retry/resolution.
    """
    __tablename__ = "dead_letter_queue"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    error_trace: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    last_error_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="dlq_entries")
    report_job: Mapped["ReportJob"] = relationship("ReportJob", back_populates="dlq_entry")
