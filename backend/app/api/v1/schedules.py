import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["schedules"])


# ── Helpers ──────────────────────────────────────────────────────────

def _to_response(schedule) -> ScheduleResponse:
    return ScheduleResponse(
        schedule_id=schedule.id,
        report_type=schedule.report_type,
        cron_expr=schedule.cron_expr,
        priority=schedule.priority,
        filters=schedule.filters,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


async def _get_schedule_or_404(
    schedule_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
):
    schedule = await schedule_service.get_schedule(
        db, schedule_id, current_user.tenant_id, current_user.id
    )
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new recurring report schedule."""
    schedule = await schedule_service.create_schedule(
        db, current_user.tenant_id, current_user.id, body
    )
    return _to_response(schedule)


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List schedules for the authenticated user. By default, only active schedules."""
    schedules = await schedule_service.list_schedules(
        db, current_user.tenant_id, current_user.id, include_inactive=include_inactive
    )
    return ScheduleListResponse(
        schedules=[_to_response(s) for s in schedules],
        total=len(schedules),
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single schedule by ID."""
    schedule = await _get_schedule_or_404(schedule_id, current_user, db)
    return _to_response(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a schedule's cron expression, priority, filters, or active flag."""
    schedule = await _get_schedule_or_404(schedule_id, current_user, db)
    updated = await schedule_service.update_schedule(db, schedule, body)
    return _to_response(updated)


@router.delete("/{schedule_id}", response_model=ScheduleResponse)
async def deactivate_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a schedule (soft delete). 
    Existing spawned jobs are preserved with their schedule_id intact.
    """
    schedule = await _get_schedule_or_404(schedule_id, current_user, db)
    deactivated = await schedule_service.deactivate_schedule(db, schedule)
    return _to_response(deactivated)