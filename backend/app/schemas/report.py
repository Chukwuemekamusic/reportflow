from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Any, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from app.db.models.report_job import ReportJob

# ── Enums as Literal types ────────────────────────────────────────────
ReportType = Literal["sales_summary", "csv_export", "pdf_report"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
RegionType = Literal["EMEA", "AMER", "APAC"]

# --- Resquest schemas ---

class ReportJobFilters(BaseModel):
    date_from: datetime | None = Field(None, examples=["2025-01-01"], description="ISO 8601 date string")
    date_to: datetime | None = Field(None, examples=["2025-01-01"], description="ISO 8601 date string")
    region: RegionType | None = None
    plan_ids: list[uuid.UUID] | None = None
    status: Literal["active", "cancelled", "all"] | None = "all"


class ReportJobCreate(BaseModel):
    """Request body for POST /api/v1/reports"""
    report_type: ReportType = Field(..., description="Type of report to generate")
    priority: int = Field(default=5, ge=1, le=9, description="1=highest, 5=normal, 9=lowest")
    idempotency_key: str | None = Field(
        None, 
        max_length=255,
        description="Optional client-generated string to avoid duplicate jobs")
    filters: dict[str, Any] | None = Field(None, description="Optional report-specific filters")
    

# --- Response schemas ---

class JobLinks(BaseModel):
    self: str
    stream: str
    download: str | None
    
class ReportJobResponse(BaseModel):
    """Response shape for job status endpoints."""
    job_id: uuid.UUID
    status: JobStatus
    report_type: ReportType
    priority: int
    progress: int = Field(0, ge=0, le=100)
    error_message: str | None = None
    retry_count: int = 0
    schedule_id: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    links: JobLinks
    
    model_config = {"from_attributes": True}
    
class ReportJobListResponse(BaseModel):
    """
    Paginated list response for job status endpoints.
    Response shape for GET /api/v1/reports
    """
    items: list[ReportJobResponse]
    total: int
    limit: int
    offset: int

class RateLimitErrorResponse(BaseModel):
    error:       str   # "rate_limit_exceeded"
    message:     str
    active_jobs: int
    

# --- Factory: build response from ORM model ---
# TODO: crossshcek the use of base_url here
def job_to_response(job: ReportJob, base_url: str = "") -> ReportJobResponse:
    """Converts a ReportJob ORM instance to a ReportJobResponse Pydantic model."""
    # Convert HTTP base_url to WebSocket URL (http -> ws, https -> wss)
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    return ReportJobResponse(
        job_id=job.id,
        status=job.status,
        report_type=job.report_type,
        priority=job.priority,
        progress=job.progress,
        error_message=job.error_message,
        retry_count=job.retry_count,
        schedule_id=job.schedule_id,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        links=JobLinks(
            self=f"{base_url}/api/v1/reports/{job.id}",
            stream=f"{ws_url}/api/v1/reports/{job.id}/stream",
            download=f"{base_url}/api/v1/reports/{job.id}/download" if job.status == "completed" else None,
        ),
    )
    
    