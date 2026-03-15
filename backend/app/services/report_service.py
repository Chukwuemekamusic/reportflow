import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.report_job import ReportJob
from app.db.models.user import User
from app.core.config import get_settings
from app.schemas.report import ReportJobCreate

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
    if payload.idempotency_key:
        result = await db.execute(
            select(ReportJob)
            .where(ReportJob.tenant_id == current_user.tenant_id)
            .where(ReportJob.idempotency_key == payload.idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"Idempotent job found: {existing.id}")
            return existing, False
        
    # ── 2. Create new job ─────────────────────────────────────────────
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
    await db.flush()
    
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

async def get_job(job_id: str, current_user: User, db: AsyncSession, ) -> ReportJob | None:
    """
    Fetch a job by ID, scoped to the current user's tenant.
    Returns None if job doesn't exist or belongs to a different tenant.
    """
    result = await db.execute(
        select(ReportJob).where(
            ReportJob.id == job_id,
            ReportJob.tenant_id == current_user.tenant_id,
        )
    )
    return result.scalar_one_or_none()
    
        
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
    """
    job = await get_job(job_id, current_user, db)
    if not job:
        return None
    if job.status not in ("queued", "running"):
        logger.warning(f"Cannot cancel job {job_id} — not queued/running")
        return job
    
    # revoke the celery task
    if job.celery_task_id:
        from celery import current_app as celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)
    
    await db.execute(
        update(ReportJob).where(ReportJob.id == job_id).values(
            status="cancelled",
        )
    )
    
    await db.commit()
    return job

