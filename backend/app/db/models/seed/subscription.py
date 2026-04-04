import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Integer, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.seed.customer import Customer
    from app.db.models.seed.plan import Plan


class Subscription(UUIDMixin, TimestampMixin, Base):
    """Subscription model linking customers to plans for demo seed data"""

    __tablename__ = "subscriptions"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )  # active, cancelled, trialing, past_due
    billing_cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )  # monthly, yearly
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mrr: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # Monthly Recurring Revenue
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="subscriptions"
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")
