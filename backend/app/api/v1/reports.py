from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.db.models.user import User
from app.schemas.report import (
    ReportJobCreate, 
    ReportJobResponse, ReportJobListResponse, 
    job_to_response,
    ReportJobFilters, )
from app.services import report_service

# websocket
import asyncio, json 
from fastapi import WebSocket, WebSocketDisconnect, status as ws_status
import redis.asyncio as aioredis
from app.core.security import decode_access_token
from app.core.config import get_settings
from app.core.rate_limit import check_and_increment_active_jobs

settings = get_settings()

router = APIRouter()

@router.post("", response_model=ReportJobResponse, status_code=status.HTTP_201_CREATED, summary="Submit a new report gemneration job")
async def submit_report(
    payload: ReportJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new async report generation job.
    
    Rate limiting is applied inside the service layer, before the DB insert,
    so there is nothing to roll back if the limit is exceeded.
    
    Returns 201 if a new job was created, or 200 if an existing job was
    returned due to an idempotency key match.
    """
    # RateLimitExceeded is raised inside create_report_job (before any DB write)
    # if the user already has max_concurrent_jobs_per_user active jobs.
    # The exception propagates here and FastAPI returns 429 automatically.
    job, created = await report_service.create_report_job(payload, current_user, db)
    response = job_to_response(job)
    if not created:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=response.model_dump(mode="json"),
            status_code=status.HTTP_200_OK,
        )
    
    return response

@router.get("", response_model=ReportJobListResponse, summary="List report jobs for current user")
async def list_report_jobs(
    status: str | None = Query(None, description="Filter by job status"),
    report_type: str | None = Query(None, description="Filter by report type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List report jobs for the current user, with optional filtering and
    pagination.
    """
    jobs = await report_service.list_jobs(current_user, db, status, report_type, limit, offset)
    return ReportJobListResponse(
        items=[job_to_response(job) for job in jobs],
        total=len(jobs),
        limit=limit,
        offset=offset,
    )
    
@router.get(
    "/{job_id}",
    response_model=ReportJobResponse,
    summary="Get job status and progress",
)
async def get_report_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status and progress of a specific report job.
    """
    job = await report_service.get_job(job_id, current_user, db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_response(job)

@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a queued or running job",
)
async def cancel_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a queued or running report job. 
    - Queued jobs: revoked from Celery queue before they start
    - Running jobs: SIGTERM sent to the worker executing the task
    - Completed/failed jobs: status updated to 'cancelled' (no-op on Celery side)

    Always returns 200 if the job belongs to the user, even if already complete.
    Returns 404 if the job does not exist or belongs to another tenant.
    """
    job = await report_service.cancel_job(job_id, current_user, db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    if job.status not in ("queued", "running", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Job cannot be cancelled - current status: {job.status}")
    


@router.get(
    "/{job_id}/download",
    summary="Download a completed report file (redirects to presigned URL)",
)
async def download_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await report_service.get_job(job_id, current_user, db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report is not ready (status: {job.status})"
        )
        
    if not job.result_file_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File key missing — contact support")
    
    # Determine extension from the object key
    ext = job.result_file_key.rsplit(".", 1)[-1] if "." in job.result_file_key else "bin"
    filename = f"report-{job_id[:8]}.{ext}"

    from app.services.storage_service import generate_presigned_url
    url = await generate_presigned_url(job.result_file_key, filename_hint=filename)
    
    # 302 REDIRECT - client will follow the redirect to the presigned URL
    return RedirectResponse(url, status_code=302)


# ── WebSocket progress stream ────────────────────────────────────────
@router.websocket("/{job_id}/stream")
async def stream_report_progress(
    websocket: WebSocket,
    job_id: str,
    token: str | None = Query(None), # passed as ?token=xyz...
):
    """
    WebSocket endpoint — streams real-time progress events for a report job.

    Flow:
      1. Validate JWT from query param (browsers can't send custom WS headers)
      2. Verify the job exists and belongs to the requesting user's tenant
      3. Subscribe to Redis pub/sub channel job:{job_id}
      4. Forward each event as a JSON text frame
      5. Close on "completed" / "failed" event, or on client disconnect
    """
    # Accept connection first (required before sending close codes with reasons)
    await websocket.accept()

    # 1. Validate JWT from query param
    if not token:
        await websocket.close(code=ws_status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return
    
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=ws_status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
    
    tenant_id = payload.get("tenant_id")

    # 2. Verify the job exists and belongs to the tenant
    from app.db.base import AsyncSessionLocal
    from app.db.models.report_job import ReportJob
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ReportJob).where(
                ReportJob.id == job_id,
                ReportJob.tenant_id == tenant_id,
            )
        )
        job = result.scalar_one_or_none()

    if not job:
        await websocket.close(code=ws_status.WS_1008_POLICY_VIOLATION, reason="Job not found")
        return
    
    # 3. If job already finished, send final event and close
    
    if job.status == "completed":
        await websocket.send_text(json.dumps({
            "event": "completed",
            "job_id": job_id,
            "progress": 100,
            "download_url": f"/api/v1/reports/{job_id}/download",
        }))
        await websocket.close()
        return
    
    if job.status == "failed":
        await websocket.send_text(json.dumps({
            "event": "failed",
            "job_id": job_id,
            "error_message": job.error_message or "Unknown error",
        }))
        await websocket.close()
        return

    # 4. Subscribe to Redis pub/sub channel and stream events
    redis_client = aioredis.Redis.from_url(settings.redis_pubsub_url, decode_responses=True)
    
    try:
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(f"job:{job_id}")
            
            async for message in pubsub.listen():
                # pubsub.listen() yields control messages (subscribe, unsubscribe, etc.) - skip them
                if message["type"] != "message":
                    continue
                
                data = message["data"]
                
                try:
                    await websocket.send_text(data)
                except WebSocketDisconnect:
                    break
                
                # parse the event to decide whether to close 
                try: 
                    event = json.loads(data)
                    if event.get("event") in ("completed", "failed"):
                        await websocket.close()
                        break
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        await redis_client.close()
                