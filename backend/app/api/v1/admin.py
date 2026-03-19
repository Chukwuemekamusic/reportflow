from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models.report_job import ReportJob
from app.db.models.dead_letter import DeadLetterQueue
from app.core.dependencies import get_db, require_admin
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

@router.get("/dlq", summary="List all dead letter queue entries")
async def list_dlq(
    resolved: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    List dead letter queue entries.
    By default returns only unresolved entries (resolved=False).
    Admins can pass ?resolved=true to see resolved entries.
    """
    print(f"DEBUG: resolved={resolved}, limit={limit}, offset={offset}")
    result = await db.execute(
        select(DeadLetterQueue)
        .where(DeadLetterQueue.resolved == resolved)
        .order_by(DeadLetterQueue.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    print(f"DEBUG: Found {len(entries)} entries")

    items = []
    for entry in entries:
        try:
            item = {
                "id": str(entry.id),
                "job_id": str(entry.job_id),
                "tenant_id": str(entry.tenant_id),
                "retry_count": entry.retry_count,
                "last_error_at": entry.last_error_at.isoformat() if entry.last_error_at else None,
                "error_trace": entry.error_trace,
                "resolved": entry.resolved,
                "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            items.append(item)
        except Exception as e:
            print(f"DEBUG: Error serializing entry {entry.id}: {e}")

    print(f"DEBUG: Serialized {len(items)} items")

    return {
        "items": items,
        "total": len(entries),
        "limit": limit,
        "offset": offset,
    }
    

# POST /admin/dlq/{id}/retry
@router.post("/dlq/{id}/retry", summary="Retry a dead letter queue entry")
async def retry_dlq(
    id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Re-enqueue the original report job from a DLQ entry.
    Creates a NEW report_jobs row (clone of the original) and enqueues it.
    Marks the DLQ entry as resolved.
    """
    
    # ── 1. Load the DLQ entry ───────────────────────────────────────────
    result = await db.execute(
        select(DeadLetterQueue).where(DeadLetterQueue.id == id)
    )
    dlq_entry = result.scalar_one_or_none()
    if not dlq_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLQ entry not found")
    if dlq_entry.resolved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DLQ entry already resolved")
    
    # ── 2. Load the original report job to clone its parameters ──────────
    result = await db.execute(
        select(ReportJob).where(ReportJob.id == dlq_entry.job_id)
    )
    original_job = result.scalar_one_or_none()
    if not original_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original job not found")
    
    # ── 3. Create a new report job as a clone of the original ───────────
    new_job = ReportJob(
        tenant_id=original_job.tenant_id,
        user_id=original_job.user_id,
        report_type=original_job.report_type,
        priority=original_job.priority,
        filters=original_job.filters,
        status="queued",
        progress=0,
        retry_count=0
        # intentionally omit idempotency_key → new job
    )
    db.add(new_job)
    await db.flush()  # flush to get new_job.id before enqueuing
    
    # ── 4. Enqueue the new job via Celery ───────────────────────────────
    from app.workers.celery_app import get_queue_for_priority
    from app.workers.tasks import TASK_MAP # {"sales_summary": run_sales_summary, ...}
    task_fn = TASK_MAP[original_job.report_type]
    if not task_fn:
        raise HTTPException(status_code=status.HTTP_400_NOT_FOUND, detail=f"Unknown report_type: {original_job.report_type}")
    
    celery_task = task_fn.apply_async(
        kwargs={
            "job_id": str(new_job.id),
            "tenant_id": str(new_job.tenant_id),
            "filters": new_job.filters or {},
        },
        queue=get_queue_for_priority(new_job.priority),
        priority=new_job.priority,
    )
    new_job.celery_task_id = celery_task.id
    
    # ── 5. Mark the DLQ entry as resolved ───────────────────────────────
    dlq_entry.resolved = True
    dlq_entry.resolved_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {
        "new_job_id": str(new_job.id),
        "dlq_entry_id": str(dlq_entry.id),
        "status": "queued",
        "message": "DLQ entry retried",
    }
    

# DELETE /admin/dlq/{id}
@router.delete("/dlq/{id}", summary="Purge a dead letter queue entry", status_code=status.HTTP_204_NO_CONTENT)
async def purge_dlq_entry(
    dlq_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """
    Mark a DLQ entry as resolved without re-running the job.
    The original failed job remains in report_jobs with status='failed'.
    """
    result = await db.execute(
        select(DeadLetterQueue).where(DeadLetterQueue.id == dlq_id)
    )
    dlq_entry = result.scalar_one_or_none()
    if not dlq_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLQ entry not found")
    
    dlq_entry.resolved = True
    dlq_entry.resolved_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {
        "dlq_entry_id": str(dlq_entry.id),
        "status": "purged",
        "message": "DLQ entry purged",
    }

