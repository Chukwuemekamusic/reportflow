import io
from datetime import datetime, timezone
import aioboto3
from botocore.exceptions import ClientError
from app.core.config import get_settings
import asyncio as _asyncio
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Object key convention ─────────────────────────────────────────────
# reports/{tenant_id}/{YYYY}/{MM}/{job_id}.{ext}
# Example: reports/abc-123/2026/03/rpt-xyz.pdf

def build_object_key(tenant_id: str, job_id: str, extension: str) -> str:
    now = datetime.now(timezone.utc)
    return f"reports/{tenant_id}/{now.year}/{now.month:02}/{job_id}.{extension}"

# ── Session factory ────────────────────────────────────────────────────
def _get_session():
    """Returns a configured aioboto3 session pointing at MinIO or S3."""
    return aioboto3.Session(
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )
    
def _get_client_kwargs() -> dict:
    """Returns endpoint_url for MinIO; omit for real AWS S3."""
    kwargs = {}
    if settings.storage_backend == "minio":
        kwargs["endpoint_url"] = settings.minio_endpoint
    return kwargs

# ── Bucket initialisation ─────────────────────────────────────────────
async def ensure_bucket_exists():
    """Ensures the configured bucket exists, creates if not."""
    session = _get_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        try:
            await s3.head_bucket(Bucket=settings.minio_bucket)
            logger.info(f"Bucket exists: {settings.minio_bucket}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404","NoSuchBucket"):
                await s3.create_bucket(Bucket=settings.minio_bucket)
                logger.info(f"Created bucket: {settings.minio_bucket}")
            else:
                logger.error(f"Failed to create bucket: {error_code}")
                raise

# ── Upload / download ─────────────────────────────────────────────────

async def upload_file(
    file_bytes: bytes,
    object_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload file bytes to MinIO/S3.
    Returns the object_key on success (stored in report_jobs.result_file_key).
    """
    session = _get_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        await s3.put_object(
            Bucket=settings.minio_bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.info(f"Uploaded {len(file_bytes)} bytes to {object_key}")
        return object_key
    
# presigned download url
async def generate_presigned_download_url(object_key: str, expires_in: int | None = None ) -> str:
    """
    Generate a time-limited presigned URL for direct client download.
    expires_in: seconds until URL expires (defaults to settings.file_expiry_seconds)
    """
    expiry_seconds = expires_in or settings.file_expiry_seconds
    session = _get_session()
    async with session.client("s3", **_get_client_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": settings.minio_bucket, "Key": object_key},
            ExpiresIn=expiry_seconds,
        )
    return url


# ── Sync upload for Celery tasks ──────────────────────────────────────
# Celery tasks are synchronous. We provide a sync wrapper so tasks don't
# need to call asyncio.run() themselves for the upload step.
def upload_file_sync(
    file_bytes: bytes,
    object_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Sync wrapper for upload_file(), safe to call from Celery tasks."""
    return _asyncio.run(upload_file(file_bytes, object_key, content_type))