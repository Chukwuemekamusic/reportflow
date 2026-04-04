import logging
import redis as _redis
from fastapi import HTTPException, status
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db.models.report_job import ReportJob
from app.db.models.user import User
from app.db.models.schedule import Schedule
from app.core.config import get_settings
from app.schemas.report import ReportJobCreate
from app.core.rate_limit import check_and_increment_active_jobs

logger = logging.getLogger(__name__)
settings = get_settings()

async def create_report_job(
    payload: ReportJobCreate,
    current_user: User,
    db: AsyncSession,
) -> tuple[ReportJob, bool]:
    """
    Create a new report job.

    Returns (job, created) where created=False if an existing job was returned
    due to idempotency key match.

    Idempotency check order:
      1. Check DB for existing job with same tenant_id + idempotency_key
         (Redis cache check can be added in Phase 4)
      2. If found → return existing job, created=False
      3. If not found → INSERT job → enqueue Celery task → return new job, created=True
    """
    # ── 1. Idempotency check ───────────────────────────────────────────
    # Fast path: Redis cache lookup

    if payload.idempotency_key:
        cache_key = f"idempotency:{str(current_user.tenant_id)}:{payload.idempotency_key}"
        with _redis.Redis.from_url(settings.redis_url, decode_responses=True) as r:
            cached_job_id = r.get(cache_key)
        if cached_job_id:
            logger.info(f"Idempotent job found in cache: {cached_job_id}")
            existing_job = await _get_job_by_id(cached_job_id, current_user, db)
            if existing_job:
                return existing_job, False
            
    # ── 1b. DB check ───────────────────────────────────────────────────
    # DB check (covers cache misses and cache disabled)
    
    if payload.idempotency_key:
        result = await db.execute(
            select(ReportJob)
            .where(ReportJob.tenant_id == current_user.tenant_id)
            .where(ReportJob.idempotency_key == payload.idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"Idempotent job hit: {existing.id}")
            # Update the Redis cache (if enabled)
            _cache_idempotency_key(
                current_user.tenant_id, 
                payload.idempotency_key, 
                existing.id
            )
            return existing, False
        
    # ── 2. Rate limiting ───────────────────────────────────────────────
    
    allowed = check_and_increment_active_jobs(str(current_user.id))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Maximum {settings.max_concurrent_jobs_per_user} concurrent jobs allowed per user.",
                "active_jobs": settings.max_concurrent_jobs_per_user,
            },
            headers={"Retry-After": "60"},
        )
        
    # ── 3. Create new job ─────────────────────────────────────────────
    job = ReportJob(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        report_type=payload.report_type,
        idempotency_key=payload.idempotency_key,
        priority=payload.priority,
        filters=payload.filters,
        status="queued",
        progress=0,
    )
    db.add(job)
    
    try:
        await db.flush() 
    except IntegrityError:
        # Race condition: another request inserted the same key between our
        # SELECT and our INSERT. Roll back and fetch the winner.
        await db.rollback()
        result = await db.execute(
            select(ReportJob).where(
                ReportJob.tenant_id == current_user.tenant_id,
                ReportJob.idempotency_key == payload.idempotency_key,
            )
        )
        existing_job = result.scalar_one()
        return existing_job, False
    
    await db.commit()
    
    # Cache the new job's idempotency key
    if payload.idempotency_key:
        _cache_idempotency_key(
            current_user.tenant_id, 
            payload.idempotency_key, 
            job.id
        )
    
    
    # ── 3. Enqueue Celery task ─────────────────────────────────────────
    # Import here to avoid circular imports at module load time
    from app.workers.celery_app import get_queue_for_priority
    
    task_map = {
        "sales_summary": "app.workers.tasks.sales_summary.run_sales_summary",
        "csv_export": "app.workers.tasks.csv_export.run_csv_export",
        "pdf_report": "app.workers.tasks.pdf_report.run_pdf_report",
    }
    
    task_name = task_map[payload.report_type]
    queue = get_queue_for_priority(payload.priority)
    
    # from app.workers.celery_app import celery_app
    from celery import current_app as celery_app
    celery_result = celery_app.send_task(
        task_name,
        kwargs={
            "job_id": str(job.id),
            "tenant_id": str(current_user.tenant_id),
            "filters": payload.filters or {},
        },
        queue=queue,
        priority=payload.priority,
    )
    
    # store celery task id for later reference
    job.celery_task_id = celery_result.task_id
    await db.commit()
    
    logger.info(f"Created job {job.id} ({payload.report_type}) → queue: {queue}")
    return job, True

async def get_job(job_id: str, current_user: User, db: AsyncSession) -> ReportJob | None:
    """
    Fetch a job by ID, scoped to the current user's tenant.
    Returns None if the job doesn't exist or belongs to a different tenant.
    """
    return await _get_job_by_id(job_id, current_user, db)
    
        
async def list_jobs(
    current_user: User,
    db: AsyncSession,
    status_filter: str | None = None,
    report_type_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReportJob]:
    """
    List all jobs for the current user's tenant, with optional filtering.
    """
    query = select(ReportJob).where(
        ReportJob.user_id == current_user.id,
        ReportJob.tenant_id == current_user.tenant_id,
    )
    
    if status_filter:
        query = query.where(ReportJob.status == status_filter)
    if report_type_filter:
        query = query.where(ReportJob.report_type == report_type_filter)
    
    query = query.order_by(ReportJob.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()

async def cancel_job(job_id: str, current_user: User, db: AsyncSession) -> ReportJob | None:
    """
    Cancel a queued or running job. 
    Revokes the celery task and marks the job as cancelled.
    Returns the updated job or None if not found.
    
    Note: jobs in terminal states (completed, failed, cancelled) are returned
    as-is without modification.
    """
    job = await _get_job_by_id(job_id, current_user, db)
    if not job:
        logger.warning(f"[{job_id}] Cannot cancel job — not found")
        return None
    
    if job.status in ("completed", "failed", "cancelled"):
        logger.warning(f"[{job_id}] Cannot cancel job — status is already '{job.status}'")
        return job
        
    
    # Revoke the Celery task
    # terminate=True sends SIGTERM to a running worker process.
    # For queued jobs it simply prevents the task from being picked up.
    if job.celery_task_id:
        from celery import current_app as celery_app
        terminate = job.status == "running"
        celery_app.control.revoke(
            job.celery_task_id,
            terminate=terminate,
            signal="SIGTERM" if terminate else None,
        )
 
    # Update the job status in the database
    now = datetime.now(timezone.utc)
    await db.execute(
        update(ReportJob)
        .where(ReportJob.id == job_id)
        .values(status="cancelled", completed_at=now)
    )
    await db.commit()
 
    # Decrement the rate-limit counter — the slot is now free
    from app.core.rate_limit import decrement_active_jobs
    decrement_active_jobs(str(current_user.id))
 
    logger.info(f"[{job_id}] Cancelled")
    return job

# ── Private helpers ──────────────────────────────────────────────────────────

async def _get_job_by_id(job_id: str, current_user: User, db: AsyncSession) -> ReportJob | None:
    """Internal fetch — scoped to the current user's tenant."""
    result = await db.execute(
        select(ReportJob).where(
            ReportJob.id == job_id,
            ReportJob.tenant_id == current_user.tenant_id,
        )
    )
    return result.scalar_one_or_none()

def _cache_idempotency_key(tenant_id: str, idempotency_key: str, job_id: str) -> None:
    """Write the idempotency key → job_id mapping to Redis with a 24h TTL."""
    # Convert UUIDs to strings (SQLAlchemy may pass UUID objects)
    tenant_id_str = str(tenant_id)
    job_id_str = str(job_id)

    cache_key = f"idempotency:{tenant_id_str}:{idempotency_key}"
    try:
        with _redis.Redis.from_url(settings.redis_url, decode_responses=True) as r:
            r.setex(cache_key, settings.idempotency_cache_ttl, job_id_str)
    except Exception as e:
        # Cache write failure is non-fatal — the DB is the source of truth
        logger.warning(f"Failed to write idempotency cache for key {idempotency_key}: {e}")
        
    
async def create_job_from_schedule(db: AsyncSession, schedule: Schedule) -> ReportJob:
    """
    Create and enqueue a ReportJob from a Schedule row.
    Called exclusively by the Beat dispatcher — not by the API.
    """
    from app.workers.celery_app import celery_app, get_queue_for_priority
    
    job = ReportJob(
        tenant_id=schedule.tenant_id,
        user_id=schedule.user_id,
        schedule_id=schedule.id, # link to the schedule that spawned this job
        report_type=schedule.report_type,
        status="queued",
        priority=schedule.priority,
        filters=schedule.filters,
        # no idempotency_key — scheduled jobs are always unique runs
    )
    
    db.add(job)
    await db.flush() 
    
    task_map = {
        "sales_summary": "app.workers.tasks.sales_summary.run_sales_summary",
        "csv_export": "app.workers.tasks.csv_export.run_csv_export",
        "pdf_report": "app.workers.tasks.pdf_report.run_pdf_report",
    }
    
    task_name = task_map[schedule.report_type]
    queue = get_queue_for_priority(schedule.priority)
    
    celery_result = celery_app.send_task(
        task_name,
        kwargs={
            "job_id": str(job.id),
            "tenant_id": str(schedule.tenant_id),
            "filters": schedule.filters or {},
        },
        queue=queue,
        priority=schedule.priority,
    )
    
    job.celery_task_id = celery_result.task_id
    await db.commit()
    return job
    