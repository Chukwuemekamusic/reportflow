"""
Periodic cleanup task to purge old completed/failed jobs.

Runs daily at 03:00 UTC via Celery Beat.
Deletes jobs older than the configured retention period to prevent database bloat.
"""

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.report_job import ReportJob
from app.workers.celery_app import run_async

logger = logging.getLogger(__name__)
settings = get_settings()


@shared_task(
    name="app.workers.tasks.cleanup_jobs.cleanup_old_jobs",
    bind=True,
    max_retries=3,
    ignore_result=True,
    queue="low",
)
def cleanup_old_jobs(self) -> None:
    """
    Delete completed/failed/cancelled jobs older than retention period.

    Retention period is configured via JOB_RETENTION_DAYS env var (default: 30 days).
    Only removes jobs in terminal states (completed, failed, cancelled).
    Active jobs (queued, running) are never deleted.
    """
    run_async(_cleanup())


async def _cleanup() -> None:
    """Async implementation - separated so run_async() can call it cleanly."""
    # Get retention period from config (default 30 days)
    retention_days = settings.job_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    async with AsyncSessionLocal() as db:
        # Delete only terminal-state jobs older than retention period
        result = await db.execute(
            delete(ReportJob).where(
                ReportJob.status.in_(["completed", "failed", "cancelled"]),
                ReportJob.created_at < cutoff,
            )
        )
        await db.commit()

        deleted = result.rowcount
        if deleted > 0:
            logger.info(
                f"[cleanup] Deleted {deleted} old job(s) (older than {retention_days} days, cutoff={cutoff.isoformat()})"
            )
        else:
            logger.debug(
                f"[cleanup] No jobs to delete (retention: {retention_days} days)"
            )
