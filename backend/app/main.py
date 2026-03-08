from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.api.v1.health import router as health_router


settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager — runs on startup/shutdown
    """
    # Startup — run migrations
    print("Starting ReportFlow API...")
    # Phase 2: initialise Redis connection pool
    # Phase 2: create MinIO bucket if not exists
    yield
    # Shutdown — clean up resources if needed
    print("Shutting down ReportFlow API...")
    

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
    app.include_router(health_router, prefix="/api/v1", tags=["Health"])
    # app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    # app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports"])
    # app.include_router(schedules_router, prefix="/api/v1/schedules", tags=["Schedules"])
    # app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])

    return app

app = create_app()