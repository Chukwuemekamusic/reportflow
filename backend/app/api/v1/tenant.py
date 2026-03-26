"""
Tenant-scoped admin endpoints for tenant administrators.

These endpoints allow tenant admins (role='admin') to view and manage
data within their own tenant only. Cross-tenant access is prevented by
filtering all queries by current_user.tenant_id.

For system-wide operations across all tenants, see /api/v1/admin/* endpoints
(requires system_admin role).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models.report_job import ReportJob
from app.db.models.dead_letter import DeadLetterQueue
from app.db.models.user import User

from app.core.dependencies import get_db, get_current_admin
from app.core.config import get_settings
from datetime import datetime, timezone

settings = get_settings()

# Requires 'admin' or 'system_admin' role, but all data is scoped to current_user.tenant_id
router = APIRouter(prefix="/tenant", tags=["Tenant Admin"])


@router.get("/jobs", summary="List report jobs in current tenant")
async def list_tenant_jobs(
    status: str | None = None,
    limit: int = 25,
    offset: int = 0,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List report jobs within the current tenant only.

    Query params:
    - status: Filter by job status (queued, running, completed, failed, cancelled)
    - limit: Number of results per page (default: 25)
    - offset: Pagination offset (default: 0)

    Only jobs belonging to the current user's tenant are returned.
    """
    query = select(ReportJob).where(
        ReportJob.tenant_id == current_user.tenant_id
    ).order_by(ReportJob.created_at.desc())

    # Apply status filter if provided
    if status:
        query = query.where(ReportJob.status == status)

    # Get total count
    count_query = select(func.count()).select_from(ReportJob).where(
        ReportJob.tenant_id == current_user.tenant_id
    )
    if status:
        count_query = count_query.where(ReportJob.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [
            {
                "job_id": str(job.id),
                "tenant_id": str(job.tenant_id),
                "user_id": str(job.user_id),
                "report_type": job.report_type,
                "status": job.status,
                "priority": job.priority,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "error_message": job.error_message,
            }
            for job in jobs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/dlq", summary="List DLQ entries in current tenant")
async def list_tenant_dlq(
    resolved: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List dead letter queue entries for the current tenant.

    By default returns only unresolved entries (resolved=False).
    Pass ?resolved=true to see resolved entries.

    Only DLQ entries belonging to the current user's tenant are returned.
    """
    # Get total count for this tenant
    count_query = select(func.count()).select_from(DeadLetterQueue).where(
        DeadLetterQueue.tenant_id == current_user.tenant_id,
        DeadLetterQueue.resolved == resolved
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated entries
    result = await db.execute(
        select(DeadLetterQueue)
        .where(
            DeadLetterQueue.tenant_id == current_user.tenant_id,  # ✅ Tenant filter!
            DeadLetterQueue.resolved == resolved
        )
        .order_by(DeadLetterQueue.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()

    items = []
    for entry in entries:
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

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/dlq/{id}/retry", summary="Retry a DLQ entry (tenant-scoped)")
async def retry_tenant_dlq(
    id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-enqueue the original report job from a DLQ entry.
    Creates a NEW report_jobs row (clone of the original) and enqueues it.
    Marks the DLQ entry as resolved.

    Only allows retrying DLQ entries from the current tenant.
    """

    # ── 1. Load the DLQ entry (with tenant filter!) ─────────────────────
    result = await db.execute(
        select(DeadLetterQueue).where(
            DeadLetterQueue.id == id,
            DeadLetterQueue.tenant_id == current_user.tenant_id  # ✅ Tenant filter!
        )
    )
    dlq_entry = result.scalar_one_or_none()
    if not dlq_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DLQ entry not found in your tenant"
        )
    if dlq_entry.resolved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="DLQ entry already resolved"
        )

    # ── 2. Load the original report job to clone its parameters ─────────
    result = await db.execute(
        select(ReportJob).where(
            ReportJob.id == dlq_entry.job_id,
            ReportJob.tenant_id == current_user.tenant_id  # ✅ Tenant filter!
        )
    )
    original_job = result.scalar_one_or_none()
    if not original_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original job not found"
        )

    # ── 3. Create a new report job as a clone of the original ──────────
    new_job = ReportJob(
        tenant_id=original_job.tenant_id,
        user_id=original_job.user_id,
        report_type=original_job.report_type,
        priority=original_job.priority,
        filters=original_job.filters,
        status="queued",
        progress=0,
        retry_count=0,
    )
    db.add(new_job)
    await db.flush()
    await db.refresh(new_job)

    # ── 4. Enqueue the new job via Celery ──────────────────────────────
    from app.workers.celery_app import submit_report_task

    task_id = submit_report_task(
        job_id=str(new_job.id),
        report_type=new_job.report_type,
        filters=new_job.filters or {},
        priority=new_job.priority,
    )

    # ── 5. Mark the DLQ entry as resolved ───────────────────────────────
    dlq_entry.resolved = True
    dlq_entry.resolved_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "message": "Job re-enqueued successfully",
        "new_job_id": str(new_job.id),
        "celery_task_id": task_id,
        "dlq_entry_id": str(dlq_entry.id),
    }


@router.delete("/dlq/{id}", summary="Delete a DLQ entry (tenant-scoped)")
async def delete_tenant_dlq(
    id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a DLQ entry.

    Only allows deleting DLQ entries from the current tenant.
    """
    result = await db.execute(
        select(DeadLetterQueue).where(
            DeadLetterQueue.id == id,
            DeadLetterQueue.tenant_id == current_user.tenant_id  # ✅ Tenant filter!
        )
    )
    dlq_entry = result.scalar_one_or_none()

    if not dlq_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DLQ entry not found in your tenant"
        )

    await db.delete(dlq_entry)
    await db.commit()

    return {"message": "DLQ entry deleted successfully", "id": str(id)}


@router.get("/stats", summary="Get tenant statistics")
async def get_tenant_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics for the current tenant:
    - Total jobs
    - Jobs by status
    - DLQ entry count
    """
    # Count jobs by status
    jobs_query = select(
        ReportJob.status,
        func.count(ReportJob.id).label("count")
    ).where(
        ReportJob.tenant_id == current_user.tenant_id
    ).group_by(ReportJob.status)

    jobs_result = await db.execute(jobs_query)
    jobs_by_status = {row.status: row.count for row in jobs_result}

    # Count total jobs
    total_jobs = sum(jobs_by_status.values())

    # Count unresolved DLQ entries
    dlq_query = select(func.count()).select_from(DeadLetterQueue).where(
        DeadLetterQueue.tenant_id == current_user.tenant_id,
        DeadLetterQueue.resolved == False
    )
    dlq_result = await db.execute(dlq_query)
    unresolved_dlq_count = dlq_result.scalar()

    return {
        "tenant_id": str(current_user.tenant_id),
        "total_jobs": total_jobs,
        "jobs_by_status": jobs_by_status,
        "unresolved_dlq_entries": unresolved_dlq_count,
    }
