import logging
from datetime import datetime, timezone, timedelta
from celery import Task
import redis as redis_sync
from app.core.config import get_settings
from app.workers.celery_app import run_async
from app.core.rate_limit import decrement_active_jobs

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 30

# Sync redis client for pub/sub publish from celery workers
_redis_client = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
_pubsub_client = redis_sync.Redis.from_url(settings.redis_pubsub_url, decode_responses=True)

class ReportBaseTask(Task):
    """
    Base class for all ReportFlow Celery tasks.

    Provides:
      - update_progress(): updates DB status + publishes WS event
      - on_success(): marks job completed, sets file key + expiry
      - on_failure(): marks job failed, inserts DLQ entry
      - on_retry(): increments retry_count in DB

    All subclasses must call self.update_progress() at meaningful stages.
    """
    abstract = True
    
    # progress reporting
    def update_progress(self, job_id: str, progress: int, stage: str, eta_secs: int = 0):
        """
        1. UPDATE report_jobs SET progress=%, status='running' WHERE id=job_id
        2. PUBLISH progress event to Redis channel job:{job_id}
        """
        run_async(self._async_update_progress(job_id, progress))
        self._publish_event(
            job_id, {
                "event": "progress",
                "job_id": job_id,
                "progress": progress,
                "stage": stage,
                "eta_secs": eta_secs,
            }
        )
        logger.info(f"[{job_id}] Progress: {progress}% — {stage}")
        
    async def _async_update_progress(self, job_id: str, progress: int):
        from app.db.base import AsyncSessionLocal
        from app.db.models.report_job import ReportJob
        from sqlalchemy import update, func

        async with AsyncSessionLocal() as session:
            
            # started_at uses COALESCE to set once on first progress update, never overwrite
            await session.execute(
                update(ReportJob).where(ReportJob.id == job_id).values(
                    progress=progress,
                    status="running",
                    started_at=func.coalesce(ReportJob.started_at, datetime.now(timezone.utc)),
                )
            )
            await session.commit()
            
            
    # Retry configuration (Parent class methods)

    def apply_async(self, args=None, kwargs=None, **options):
        """
        Override apply_async to attach retry configuration.
        Sets max_retries and the countdown for the first retry.
        """
        options.setdefault("max_retries", MAX_RETRIES)
        options.setdefault("countdown", RETRY_BACKOFF_BASE_SECONDS)
        return super().apply_async(args=args, kwargs=kwargs, **options)

    def retry(self, args=None, kwargs=None, exc=None, **options):
        """
        Override retry to compute exponential backoff countdown.
        Backoff formula: base_seconds * (4 ^ attempt)
        - Attempt 1: 30s
        - Attempt 2: 120s (30 * 4)
        - Attempt 3: 480s (30 * 16)
        """
        attempt = self.request.retries  # 0-indexed: 0 means first retry
        countdown = RETRY_BACKOFF_BASE_SECONDS * (4 ** attempt)
        options.setdefault("countdown", countdown)
        options.setdefault("max_retries", MAX_RETRIES)
        return super().retry(args=args, kwargs=kwargs, exc=exc, **options)

    # Lifecycle hooks

    def on_success(self, retval, task_id, args, kwargs):
        """
        Called by Celery after the task function returns successfully.
        retval is the return value from the task function — expected to be
        the MinIO object key (e.g. "reports/tenant-id/2026/03/job-id.pdf")
        """

        job_id = kwargs.get('job_id')
        if not job_id:
            logger.error(f"job_id not found in kwargs: {kwargs}")
            return
        try:
            run_async(self._async_on_success(job_id, retval))
        except Exception as e:
            logger.error(f"[{job_id}] Failed to update job status on success: {e}", exc_info=True)
    
    async def _async_on_success(self, job_id: str, file_key: str):
        from app.db.base import AsyncSessionLocal
        from app.db.models.report_job import ReportJob
        from sqlalchemy import update, select

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ReportJob).where(ReportJob.id == job_id).values(
                    status="completed",
                    result_file_key=file_key,
                    progress=100,
                    completed_at=now,
                    expires_at=now + timedelta(seconds=settings.file_expiry_seconds),
                )
            )
            await session.commit()

            # Fetch user_id for decrement
            result = await session.execute(
                select(ReportJob.user_id).where(ReportJob.id == job_id)
            )            
            user_id = result.scalar_one_or_none()
            
        if not user_id:
            logger.error(f"[{job_id}] Could not find user_id to decrement rate-limit counter")
            return

        # 1. Free the slot first
        decrement_active_jobs(str(user_id))

        # 2. Then notify clients (outside transaction)
        self._publish_event(job_id, {
            "event": "completed",
            "job_id": job_id,
            "progress": 100,
            "download_url": f"/api/v1/reports/{job_id}/download",
        })
        logger.info(f"[{job_id}] Completed — file key: {file_key}")
    
    def on_failure(self, exc, task_id: str, args, kwargs, einfo):
        """
        Called by Celery after all retries are exhausted.
        Updates job to failed and inserts a DLQ record.
        """
        job_id = kwargs.get("job_id")
        if not job_id:
            logger.error(f"job_id not found in kwargs: {kwargs}")
            return

        error_message = str(exc) if exc else "Unknown error"
        error_trace = str(einfo) if einfo else "No traceback available"
        try:
            run_async(self._async_on_failure(job_id, error_message, error_trace))
        except Exception as e:
             logger.error(f"[{job_id}] on_failure handler failed: {e}", exc_info=True)
        
    async def _async_on_failure(self, job_id: str, error_message: str, error_trace: str):
        from app.db.base import AsyncSessionLocal
        from app.db.models.report_job import ReportJob
        from app.db.models.dead_letter import DeadLetterQueue
        from sqlalchemy import update, select

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ReportJob).where(ReportJob.id == job_id).values(
                    status="failed",
                    error_message=error_message,
                )
            )
            result = await session.execute(
                select(ReportJob).where(ReportJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found in DB: {job_id}")
                await session.commit()
                return

            dlq = DeadLetterQueue(
                job_id=job_id,
                tenant_id=job.tenant_id,
                error_trace=error_trace,
                retry_count=job.retry_count,
                last_error_at=datetime.now(timezone.utc),
            )
            session.add(dlq)
            await session.commit()

        # 1. Free the slot first
        decrement_active_jobs(str(job.user_id))

        # 2. Then notify clients (outside transaction)
        self._publish_event(job_id, {
            "event": "failed",
            "job_id": job_id,
            "error_message": error_message,
        })
        logger.error(f"[{job_id}] Permanently failed — {error_message}")
        
    
    def on_retry(self, exc, _task_id: str, _args, kwargs, _einfo):
        """
        Called by Celery when a task is retried.
        Increments retry_count in DB.
        """
        job_id = kwargs.get("job_id")
        if not job_id:
            logger.error(f"job_id not found in kwargs: {kwargs}")
            return
        try:
            run_async(self._async_on_retry(job_id))
        except Exception as e:
            logger.error(f"[{job_id}] on_retry handler failed: {e}", exc_info=True)
        logger.warning(f"[{job_id}] Retrying after: {exc}")
        
    async def _async_on_retry(self, job_id: str):
        from app.db.base import AsyncSessionLocal
        from app.db.models.report_job import ReportJob
        from sqlalchemy import update
        
        async with AsyncSessionLocal() as session:
            
            await session.execute(
                update(ReportJob).where(ReportJob.id == job_id).values(
                    retry_count=ReportJob.retry_count + 1,
                )
            )
            await session.commit()
            
    
    # internal helpers
    def _publish_event(self, job_id: str, event_data: dict):
        """Publish a JSON event to Redis pub/sub channel job:{job_id}. (DB 1)"""
        import json
        try:
            _pubsub_client.publish(f"job:{job_id}", json.dumps(event_data))
        except Exception as e:
            logger.error(f"[{job_id}] Failed to publish event: {e}")
            
    
    
        
    
