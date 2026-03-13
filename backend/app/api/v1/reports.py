from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.db.models.user import User
from app.schemas.report import (
    ReportJobCreate, 
    ReportJobResponse, ReportJobListResponse, 
    job_to_response,
    ReportJobFilters, )
from app.services import report_service

router = APIRouter()

@router.post("", response_model=ReportJobResponse, status_code=status.HTTP_201_CREATED, summary="Submit a new report gemneration job")
async def submit_report(
    payload: ReportJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new async report generation job.

    Returns 201 if a new job was created, or 200 if an existing job was
    returned due to an idempotency key match.
    """
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
    Returns 204 No Content if successful, 404 if job not found.
    """
    job = await report_service.cancel_job(job_id, current_user, db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in ("queued", "running", "cancelled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is {job.status} and cannot be cancelled")
    