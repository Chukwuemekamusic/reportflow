from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from app.core.dependencies import get_db
from app.schemas.health import HealthResponse, ServiceStatus

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
            message=f"Database connection failed: {str(e)}"
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
