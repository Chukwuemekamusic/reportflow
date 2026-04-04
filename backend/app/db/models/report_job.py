from sqlalchemy import (
    String,
    SmallInteger,
    Text,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.user import User
    from app.db.models.schedule import Schedule
    from app.db.models.dead_letter import DeadLetterQueue


class ReportJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "report_jobs"

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
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="queued", nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="report_jobs")
    user: Mapped["User"] = relationship("User", back_populates="report_jobs")
    schedule: Mapped["Schedule"] = relationship(
        "Schedule", back_populates="report_jobs"
    )
    dlq_entry: Mapped["DeadLetterQueue"] = relationship(
        "DeadLetterQueue", back_populates="report_job", uselist=False
    )

    # ── Table-level constraints & indexes ────────────────────────────
    __table_args__ = (
        # Idempotency enforced at DB level — not just application level
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_jobs_tenant_idempotency"
        ),
        # Indexes on every column used in WHERE or ORDER BY
        Index("idx_jobs_tenant", "tenant_id"),
        Index("idx_jobs_user", "user_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created", "created_at"),
    )
