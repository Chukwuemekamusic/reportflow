"""
Health check endpoint — verifies all external dependencies are reachable.
Used by Docker health checks, load balancers, and monitoring systems.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
import boto3
from botocore.exceptions import ClientError, EndpointResolutionError
from datetime import datetime

from app.core.dependencies import get_db
from app.core.config import get_settings
from app.schemas.health import HealthResponse, ServiceStatus

settings = get_settings()
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Returns the health status of the API and its dependencies (database, Redis, MinIO)"
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Check health status of the application and its dependencies.

    Returns:
        HealthResponse with overall status and individual service statuses
    """
    services = {}

    # Check database connection
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        services["database"] = ServiceStatus(
            status="healthy",
            message="Database connection successful"
        )
    except Exception as e:
        services["database"] = ServiceStatus(
            status="unhealthy",
            message=f"Database connection failed: {str(e)[:80]}"
        )
        
    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        services["redis"] = ServiceStatus(
            status="healthy",
            message="Redis connection successful"
        )
    except Exception as e:
        services["redis"] = ServiceStatus(
            status="unhealthy",
            message=f"Redis connection failed: {str(e)[:80]}"
        )
    
    # Minio / S3
    try:
        import aioboto3
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
        ) as s3:
            await s3.head_bucket(Bucket=settings.minio_bucket)
        services["storage"] = ServiceStatus(
            status="healthy",
            message="Redis connection successful"
        )
    except Exception as e:
        services["storage"] = ServiceStatus(
            status="unhealthy",
            message=f"Database connection failed: {str(e)[:80]}"
        )
        

    # Determine overall status 
    overall_status = "healthy" if all(
        service.status == "healthy" for service in services.values()
    ) else "unhealthy"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services,
        version="0.1.0"
    )
    
    
    
    
# @router.get("/health")
# async def health_check(db: AsyncSession = Depends(get_db)):
#     """
#     Returns 200 if the API is running and DB is reachable.
#     Returns 503 if any dependency is unhealthy.
#     """
#     try:
#         await db.execute(text("SELECT 1"))
#         db_status = "healthy"
#     except Exception as e:
#         db_status = f"unhealthy: {str(e)}"

#     return {
#         "status": "ok" if db_status == "healthy" else "degraded",
#         "database": db_status,
#         "version": "1.0.0",
#     }
