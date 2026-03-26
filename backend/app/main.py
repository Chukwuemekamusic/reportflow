from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.core.config import get_settings
from app.services.storage_service import ensure_bucket_exists

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager — runs on startup/shutdown
    """
    # Startup
    logger.info("Starting ReportFlow API...")
    # Phase 2: initialise Redis connection pool
    # Phase 2: create MinIO bucket if not exists
    await ensure_bucket_exists()
    logger.info("ReportFlow API startup complete")
    yield
    # Shutdown — clean up resources if needed
    logger.info("Shutting down ReportFlow API...")
    

def create_app() -> FastAPI:
    app = FastAPI(
        title="ReportFlow API",
        description="Backend API for ReportFlow",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Routers
    from app.api.v1.health import router as health_router
    from app.api.v1.auth import router as auth_router
    from app.api.v1.reports import router as reports_router
    from app.api.v1.admin import router as admin_router
    from app.api.v1.schedules import router as schedules_router
    from app.api.v1.users import router as users_router
    from app.api.v1.tenant import router as tenant_router

    app.include_router(health_router, prefix="/api/v1", tags=["Health"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(tenant_router, prefix="/api/v1", tags=["Tenant Admin"])
    app.include_router(admin_router, prefix="/api/v1", tags=["System Admin"])
    app.include_router(schedules_router, prefix="/api/v1", tags=["Schedules"])

    return app

app = create_app()