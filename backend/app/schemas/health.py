from pydantic import BaseModel, Field
from datetime import datetime


class ServiceStatus(BaseModel):
    """Individual service health status"""

    status: str = Field(..., description="Service status: healthy or unhealthy")
    message: str = Field(..., description="Status message or error details")


class HealthResponse(BaseModel):
    """Overall health check response"""

    status: str = Field(..., description="Overall status: healthy or unhealthy")
    timestamp: datetime = Field(..., description="Health check timestamp (UTC)")
    services: dict[str, ServiceStatus] = Field(
        ..., description="Status of individual services"
    )
    version: str = Field(..., description="API version")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "services": {
                    "database": {
                        "status": "healthy",
                        "message": "Database connection successful",
                    }
                },
                "version": "0.1.0",
            }
        }
    }
