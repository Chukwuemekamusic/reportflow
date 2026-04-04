from sqlalchemy import String, Numeric, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.seed.subscription import Subscription


class Plan(UUIDMixin, TimestampMixin, Base):
    """Subscription plan/tier model for demo seed data"""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_yearly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan"
    )
