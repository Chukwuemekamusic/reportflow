from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base
from app.db.models.mixins import UUIDMixin, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.schedule import Schedule
    from app.db.models.report_job import ReportJob


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Role: "member" | "admin" | "system_admin"
    # - member: Regular user within a tenant
    # - admin: Tenant administrator (can manage users, view tenant data)
    # - system_admin: Platform operator (can view all tenants, access /admin/* endpoints)
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="user"
    )
    report_jobs: Mapped[list["ReportJob"]] = relationship(
        "ReportJob", back_populates="user"
    )

    # Compound unique: email must be unique within a tenant, not globally
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_tenant_email"),)
