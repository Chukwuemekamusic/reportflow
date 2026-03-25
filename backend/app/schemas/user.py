from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from datetime import datetime
import uuid


# ── Request Schemas ────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    """Request body for POST /api/v1/users (admin creates new user in tenant)"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password (min 8 characters)")
    role: Literal["member", "admin"] = Field(default="member", description="User's role within the tenant")


# ── Response Schemas ────────────────────────────────────────────

class UserResponse(BaseModel):
    """Response shape for user endpoints"""
    id: uuid.UUID
    email: str
    role: str
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list response for GET /api/v1/users"""
    items: list[UserResponse]
    total: int
    limit: int
    offset: int
