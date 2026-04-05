from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars like TOKEN
    )

    # Application
    app_env: str = "development"
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]

    # Database
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://redis:6379/0"
    redis_pubsub_url: str | None = "redis://redis:6379/1"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/2"
    celery_task_max_retries: int = 3
    celery_task_timeout_seconds: int = 600
    beat_schedule_interval: float = (
        60.0  # seconds - how often Beat checks for due schedules
    )
    job_retention_days: int = (
        30  # days - how long to keep completed/failed jobs before cleanup
    )

    # File Storage (MinIO / S3)
    storage_backend: str = "minio"
    minio_endpoint: str = "http://minio:9000"
    minio_public_endpoint: str | None = (
        None  # Public-facing endpoint for presigned URLs (e.g., http://localhost:9000)
    )
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "reportflow-files"
    file_expiry_seconds: int = 86400  # 24 hours
    idempotency_cache_ttl: int = 86400  # 24 hours

    # Rate Limiting
    max_concurrent_jobs_per_user: int = 5

    # Seed
    seed_customers: int = 500
    seed_subscriptions: int = 1200


@lru_cache()
def get_settings():
    return Settings()
