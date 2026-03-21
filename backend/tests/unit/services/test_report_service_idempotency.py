"""
Unit tests for idempotency caching in report service.

Tests the Redis cache layer for idempotency keys, including:
- Cache write on job creation
- Cache hit on duplicate requests (fast path)
- Cache miss fallback to DB
- Correct UUID-to-string conversion
- TTL configuration
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
from app.services.report_service import create_report_job, _cache_idempotency_key
from app.schemas.report import ReportJobCreate


@pytest.mark.asyncio
async def test_create_job_caches_idempotency_key_in_redis():
    """Test that creating a job writes the idempotency key to Redis with correct TTL."""
    # Arrange
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    current_user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
    )

    payload = ReportJobCreate(
        report_type="sales_summary",
        priority=5,
        idempotency_key="test-key-123",
        filters={},
    )

    # Mock Redis to return no cached job (cache miss)
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = None
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)

    # Mock DB to return no existing job
    result_mock = Mock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    # Track the created job and assign ID when added (simulating DB behavior)
    created_job_ref = []

    def add_job(job):
        # SQLAlchemy assigns ID during flush, but for testing we assign it here
        # so it's available when the cache is written
        job.id = job_id
        created_job_ref.append(job)

    # db.add is called WITHOUT await, so it must be a synchronous Mock
    db.add = Mock(side_effect=add_job)

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.idempotency_cache_ttl = 86400
            mock_settings.max_concurrent_jobs_per_user = 5

            with patch("app.services.report_service.check_and_increment_active_jobs", return_value=True):
                with patch("celery.current_app") as mock_celery:
                    mock_celery.send_task.return_value = Mock(task_id="celery-task-123")

                    # Act
                    job, created = await create_report_job(payload, current_user, db)

    # Assert - verify Redis setex was called with correct parameters
    expected_cache_key = f"idempotency:{str(tenant_id)}:test-key-123"

    # The cache should be written with the job_id
    mock_redis_instance.setex.assert_called_once()
    call_args = mock_redis_instance.setex.call_args[0]
    assert call_args[0] == expected_cache_key
    assert call_args[1] == 86400
    assert call_args[2] == str(job_id)


@pytest.mark.asyncio
async def test_create_job_returns_cached_job_on_redis_hit():
    """Test that a Redis cache hit returns the existing job without DB query."""
    # Arrange
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cached_job_id = uuid.uuid4()

    current_user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
    )

    payload = ReportJobCreate(
        report_type="sales_summary",
        priority=5,
        idempotency_key="test-key-cached",
        filters={},
    )

    # Mock Redis to return a cached job ID
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = str(cached_job_id)
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)

    # Mock DB to return the cached job when queried by ID
    existing_job = SimpleNamespace(
        id=cached_job_id,
        tenant_id=tenant_id,
        status="completed",
        idempotency_key="test-key-cached",
    )
    result_mock = Mock()
    result_mock.scalar_one_or_none.return_value = existing_job
    db.execute.return_value = result_mock

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            # Act
            job, created = await create_report_job(payload, current_user, db)

    # Assert
    assert created is False
    assert job.id == cached_job_id
    assert job.idempotency_key == "test-key-cached"

    # Verify we checked Redis first
    expected_cache_key = f"idempotency:{str(tenant_id)}:test-key-cached"
    mock_redis_instance.get.assert_called_once_with(expected_cache_key)


@pytest.mark.asyncio
async def test_create_job_falls_back_to_db_on_cache_miss():
    """Test that cache miss falls back to DB query and returns existing job."""
    # Arrange
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    existing_job_id = uuid.uuid4()

    current_user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
    )

    payload = ReportJobCreate(
        report_type="sales_summary",
        priority=5,
        idempotency_key="test-key-db-fallback",
        filters={},
    )

    # Mock Redis to return None (cache miss)
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = None
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)

    # Mock DB to return existing job on idempotency check
    existing_job = SimpleNamespace(
        id=existing_job_id,
        tenant_id=tenant_id,
        status="queued",
        idempotency_key="test-key-db-fallback",
    )
    result_mock = Mock()
    result_mock.scalar_one_or_none.return_value = existing_job
    db.execute.return_value = result_mock

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.idempotency_cache_ttl = 86400

            # Act
            job, created = await create_report_job(payload, current_user, db)

    # Assert
    assert created is False
    assert job.id == existing_job_id

    # Verify cache was updated with the DB result
    expected_cache_key = f"idempotency:{str(tenant_id)}:test-key-db-fallback"
    mock_redis_instance.setex.assert_called_once_with(
        expected_cache_key,
        86400,
        str(existing_job_id),
    )


def test_cache_idempotency_key_converts_uuid_to_string():
    """Test that _cache_idempotency_key properly converts UUID objects to strings."""
    # Arrange
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    idempotency_key = "test-key-uuid"

    mock_redis_instance = MagicMock()
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.idempotency_cache_ttl = 3600

            # Act - pass UUID objects (simulating SQLAlchemy behavior)
            _cache_idempotency_key(tenant_id, idempotency_key, job_id)

    # Assert - verify strings were used in Redis call
    expected_cache_key = f"idempotency:{str(tenant_id)}:{idempotency_key}"
    mock_redis_instance.setex.assert_called_once_with(
        expected_cache_key,
        3600,
        str(job_id),
    )


def test_cache_idempotency_key_handles_redis_errors_gracefully():
    """Test that Redis write failures are logged but don't raise exceptions."""
    # Arrange
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    idempotency_key = "test-key-error"

    mock_redis_instance = MagicMock()
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)
    mock_redis_instance.setex.side_effect = ConnectionError("Redis connection failed")

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.idempotency_cache_ttl = 3600

            with patch("app.services.report_service.logger") as mock_logger:
                # Act - should not raise exception
                _cache_idempotency_key(tenant_id, idempotency_key, job_id)

                # Assert - error was logged
                mock_logger.warning.assert_called_once()
                assert "Failed to write idempotency cache" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_idempotency_key_cache_format_is_correct():
    """Test that the Redis cache key follows the expected format."""
    # Arrange
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    current_user = SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
    )

    payload = ReportJobCreate(
        report_type="sales_summary",
        priority=5,
        idempotency_key="my-custom-key",
        filters={},
    )

    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = None
    mock_redis_instance.__enter__ = Mock(return_value=mock_redis_instance)
    mock_redis_instance.__exit__ = Mock(return_value=False)

    # Mock DB to return no existing job (both for cache check and idempotency check)
    result_mock = Mock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    # Mock db.add to set job.id (synchronous, not async)
    def set_job_id(job):
        job.id = uuid.uuid4()
        job.celery_task_id = None

    db.add = Mock(side_effect=set_job_id)

    with patch("app.services.report_service._redis.Redis.from_url", return_value=mock_redis_instance):
        with patch("app.services.report_service.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.idempotency_cache_ttl = 86400
            mock_settings.max_concurrent_jobs_per_user = 5

            with patch("app.services.report_service.check_and_increment_active_jobs", return_value=True):
                with patch("celery.current_app") as mock_celery:
                    mock_celery.send_task.return_value = Mock(task_id="celery-task-123")

                    # Act
                    _ = await create_report_job(payload, current_user, db)

    # Assert - verify cache key format: "idempotency:{tenant_id}:{key}"
    expected_cache_key = f"idempotency:{str(tenant_id)}:my-custom-key"
    mock_redis_instance.get.assert_called_with(expected_cache_key)
