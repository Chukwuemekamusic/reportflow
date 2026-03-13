from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    """Customer/company model for demo seed data"""
    __tablename__ = "customers"

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)  # EMEA, AMER, APAC
    industry: Mapped[str] = mapped_column(String(100), nullable=True)

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="customer")
