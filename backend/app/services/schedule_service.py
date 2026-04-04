import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from croniter import croniter

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────
def _compute_next_run(cron_expr: str, after: datetime | None = None) -> datetime | None:
    """Return the next UTC datetime for a cron expression."""
    base = after or datetime.now(timezone.utc)
    # croniter returns a naive datetime — make it timezone-aware
    nxt = croniter(cron_expr, base).get_next(datetime)
    return nxt.replace(tzinfo=timezone.utc) if nxt.tzinfo is None else nxt


# ── CRUD ─────────────────────────────────────────────────────────────


async def create_schedule(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ScheduleCreate,
) -> Schedule:
    """Create a new active schedule and compute its first next_run_at."""
    next_run = _compute_next_run(data.cron_expr)
    schedule = Schedule(
        tenant_id=tenant_id,
        user_id=user_id,
        report_type=data.report_type,
        cron_expr=data.cron_expr,
        priority=data.priority,
        filters=data.filters,
        is_active=True,
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def list_schedules(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    include_inactive: bool = False,
) -> list[Schedule]:
    """Return schedules for the authenticated user, newest first."""
    logger.info(f"Listing schedules for tenant {tenant_id} and user {user_id}")
    stmt = (
        select(Schedule)
        .where(Schedule.tenant_id == tenant_id, Schedule.user_id == user_id)
        .order_by(Schedule.created_at.desc())
    )
    if not include_inactive:
        stmt = stmt.where(Schedule.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_schedule(
    db: AsyncSession,
    schedule_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Schedule | None:
    """Return a schedule for the authenticated user, or None if not found."""
    logger.info(
        f"Getting schedule {schedule_id} for tenant {tenant_id} and user {user_id}"
    )
    stmt = select(Schedule).where(
        Schedule.id == schedule_id,
        Schedule.tenant_id == tenant_id,
        Schedule.user_id == user_id,
    )
    result = await db.execute(stmt)
    logger.info(f"Schedule found: {result.scalar_one_or_none()}")
    return result.scalar_one_or_none()


async def update_schedule(
    db: AsyncSession,
    schedule: Schedule,
    data: ScheduleUpdate,
) -> Schedule:
    """Apply partial updates to a schedule; recompute next_run_at if cron changed."""
    changed = False

    if data.cron_expr is not None and data.cron_expr != schedule.cron_expr:
        schedule.cron_expr = data.cron_expr
        # Recompute from now so the new expression fires correctly
        schedule.next_run_at = _compute_next_run(data.cron_expr)
        changed = True

    if data.priority is not None and data.priority != schedule.priority:
        schedule.priority = data.priority
        changed = True

    if data.filters is not None and data.filters != schedule.filters:
        schedule.filters = data.filters
        changed = True

    if data.is_active is not None and data.is_active != schedule.is_active:
        schedule.is_active = data.is_active
        if data.is_active:
            # Re-activating — recompute next_run_at so it doesn't fire immediately
            # for an old next_run_at that has already passed
            schedule.next_run_at = _compute_next_run(schedule.cron_expr)
        changed = True

    if changed:
        await db.commit()
        await db.refresh(schedule)

    return schedule


async def deactivate_schedule(
    db: AsyncSession,
    schedule: Schedule,
) -> Schedule:
    """Soft-delete: set is_active=False. History and spawned jobs are preserved."""
    schedule.is_active = False
    await db.commit()
    await db.refresh(schedule)
    logger.info(f"Deactivated schedule {schedule.id}")
    return schedule


# ── Beat task ───────────────────────────────────────────────────────────


async def get_due_schedules(db: AsyncSession) -> list[Schedule]:
    """
    Return all active schedules whose next_run_at is in the past.
    Called by the Beat dispatcher task every 60 seconds.
    """
    now = datetime.now(timezone.utc)
    stmt = select(Schedule).where(
        Schedule.is_active.is_(True),
        Schedule.next_run_at <= now,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_schedule_ran(db: AsyncSession, schedule: Schedule) -> None:
    """
    After a job is dispatched:
    - Set last_run_at = now
    - Advance next_run_at to the next future occurrence
    """
    now = datetime.now(timezone.utc)
    schedule.last_run_at = now
    schedule.next_run_at = _compute_next_run(schedule.cron_expr, after=now)
    logger.info(f"Marked schedule {schedule.id} as run at {now}")
    await db.commit()
