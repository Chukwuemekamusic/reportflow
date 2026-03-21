"""
Beat dispatcher task.

Runs every 60 seconds (configured in celery_app.py beat_schedule).
Finds all active schedules whose next_run_at is in the past and spawns
a report job for each one.
"""
import logging 

from celery import shared_task
from app.workers.celery_app import run_async
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)

@shared_task(
    name="app.workers.tasks.beat_schedule.dispatch_scheduled_jobs",
    bind=True,
    max_retries=0,             # failures should not retry — next run is in 60s
    ignore_result=True,        # no result backend entry needed
    queue="low",               # lightweight task; don't compete with report workers
)
def dispatch_scheduled_jobs(self) -> None:
    """
    Poll for due schedules and spawn report jobs.
    Called by Celery Beat every 60 seconds.
    """
    run_async(_dispatch())


async def _dispatch() -> None:
    """Async implementation — separated so run_async() can call it cleanly."""
    from app.services.schedule_service import get_due_schedules, mark_schedule_ran
    from app.services.report_service import create_job_from_schedule
    
    
    
    async with AsyncSessionLocal() as db:
        due = await get_due_schedules(db)
        
        if not due:
            return
        
        logger.info(f"[beat] {len(due)} schedule(s) due — dispatching jobs")
        
        for schedule in due:
            try:
                job = await create_job_from_schedule(db, schedule)
                await mark_schedule_ran(db, schedule)
                logger.info(f"[beat] Spawned job {job.id} (type={schedule.report_type}, schedule={schedule.id})")
            except Exception as exc:
                # Log and continue — don't let one failed schedule block the rest
                logger.error(f"[beat] Failed to dispatch schedule {schedule.id}: {exc}", exc_info=True)
