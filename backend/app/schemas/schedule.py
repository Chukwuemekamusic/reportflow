from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from croniter import croniter


class ScheduleCreate(BaseModel):
    report_type: str = Field(..., pattern=r"^(sales_summary|csv_export|pdf_report)$")
    cron_expr: str = Field(..., min_length=9, max_length=100, examples=["0 8 * * 1"])
    priority: int = Field(default=5, ge=1, le=9)
    filters: dict | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: '{v}'")
        return v


class ScheduleUpdate(BaseModel):
    cron_expr: str | None = Field(default=None, min_length=9, max_length=100)
    priority: int | None = Field(default=None, ge=1, le=9)
    filters: dict | None = None
    is_active: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: '{v}'")
        return v


class ScheduleResponse(BaseModel):
    schedule_id: uuid.UUID
    report_type: str
    cron_expr: str
    priority: int
    filters: dict | None
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleResponse]
    total: int
