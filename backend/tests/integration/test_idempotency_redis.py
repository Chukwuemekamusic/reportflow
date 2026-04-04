"""
Integration test for idempotency caching with real Redis.

Run this test INSIDE the Docker container:
    docker compose exec api uv run pytest tests/integration/test_idempotency_redis.py -v

This test uses the real Redis instance running in Docker.
"""
import asyncio
import redis
import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime
from app.core.config import get_settings

settings = get_settings()


@pytest_asyncio.fixture(scope="function")
def redis_client():
    """Create a Redis client for direct cache inspection."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    client.close()


@pytest.mark.asyncio
async def test_idempotency_key_is_cached_in_redis(client: AsyncClient, redis_client: redis.Redis):
    """
    Test that creating a job with an idempotency key writes to Redis cache.
    Verifies the cache key format and TTL.
    """
    timestamp = int(datetime.now().timestamp())
    email = f"redis-test-{timestamp}@example.com"
    password = "securepass123"
    tenant_name = f"RedisTest-{timestamp}"
    idempotency_key = f"redis-test-key-{timestamp}"

    # ────────────────────────────────────────────────────────────
    # Step 1: Register and login
    # ────────────────────────────────────────────────────────────
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": tenant_name,
        },
    )
    assert register_response.status_code == 201

    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ────────────────────────────────────────────────────────────
    # Step 2: Submit a report with idempotency key
    # ────────────────────────────────────────────────────────────
    submit_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {},
        },
        headers=headers,
    )
    assert submit_response.status_code == 201
    job_id = submit_response.json()["job_id"]

    # ────────────────────────────────────────────────────────────
    # Step 3: Verify Redis cache contains the idempotency key
    # ────────────────────────────────────────────────────────────
    # Find the cache key by pattern since we don't have tenant_id readily available
    cache_keys = redis_client.keys(f"idempotency:*:{idempotency_key}")
    assert len(cache_keys) == 1, f"Expected 1 cache key matching pattern, found {len(cache_keys)}"

    cache_key = cache_keys[0]
    cached_job_id = redis_client.get(cache_key)

    assert cached_job_id is not None, f"Expected cache key '{cache_key}' not found in Redis"
    assert cached_job_id == job_id, f"Cached job ID '{cached_job_id}' doesn't match actual '{job_id}'"

    # ────────────────────────────────────────────────────────────
    # Step 4: Verify TTL is set correctly (24 hours = 86400 seconds)
    # ────────────────────────────────────────────────────────────
    ttl = redis_client.ttl(cache_key)
    assert ttl > 0, f"Cache key '{cache_key}' has no TTL set"
    assert 86300 <= ttl <= 86400, f"TTL {ttl} is outside expected range (86300-86400)"


@pytest.mark.asyncio
async def test_idempotency_cache_hit_returns_same_job(client: AsyncClient, redis_client: redis.Redis):
    """
    Test that submitting the same idempotency key twice returns the cached job
    on the second request (fast path via Redis, not DB).
    """
    timestamp = int(datetime.now().timestamp())
    email = f"cache-hit-{timestamp}@example.com"
    password = "securepass123"
    tenant_name = f"CacheHitTest-{timestamp}"
    idempotency_key = f"cache-hit-key-{timestamp}"

    # ────────────────────────────────────────────────────────────
    # Setup: Register and login
    # ────────────────────────────────────────────────────────────
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": tenant_name,
        },
    )
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ────────────────────────────────────────────────────────────
    # Step 1: Submit first report
    # ────────────────────────────────────────────────────────────
    first_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {"region": "EMEA"},
        },
        headers=headers,
    )
    assert first_response.status_code == 201
    first_job_id = first_response.json()["job_id"]

    # ────────────────────────────────────────────────────────────
    # Step 2: Submit duplicate request with same idempotency key
    # ────────────────────────────────────────────────────────────
    second_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {"region": "AMER"},  # Different filters - should be ignored
        },
        headers=headers,
    )

    # ────────────────────────────────────────────────────────────
    # Step 3: Verify response returns existing job
    # ────────────────────────────────────────────────────────────
    assert second_response.status_code == 200  # 200, not 201
    second_job_id = second_response.json()["job_id"]
    assert second_job_id == first_job_id

    # Verify filters from original request are preserved (not overwritten)
    second_filters = second_response.json().get("filters", {})
    assert second_filters.get("region") == "EMEA"  # Original, not "AMER"


@pytest.mark.asyncio
async def test_cache_survives_across_multiple_requests(client: AsyncClient, redis_client: redis.Redis):
    """
    Test that the Redis cache persists across multiple rapid requests
    and consistently returns the same cached job.
    """
    timestamp = int(datetime.now().timestamp())
    email = f"multi-request-{timestamp}@example.com"
    password = "securepass123"
    idempotency_key = f"multi-request-key-{timestamp}"

    # Setup
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": f"MultiTest-{timestamp}",
        },
    )
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # First request
    first_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {},
        },
        headers=headers,
    )
    original_job_id = first_response.json()["job_id"]

    # Make 5 rapid duplicate requests
    job_ids = []
    for _ in range(5):
        response = await client.post(
            "/api/v1/reports",
            json={
                "report_type": "sales_summary",
                "priority": 5,
                "idempotency_key": idempotency_key,
                "filters": {},
            },
            headers=headers,
        )
        assert response.status_code == 200
        job_ids.append(response.json()["job_id"])

    # All responses should return the same job ID
    assert all(job_id == original_job_id for job_id in job_ids)


@pytest.mark.asyncio
async def test_cache_isolation_between_tenants(client: AsyncClient, redis_client: redis.Redis):
    """
    Test that idempotency keys are isolated per tenant.
    Same key for different tenants should create separate jobs.
    """
    timestamp = int(datetime.now().timestamp())
    shared_idempotency_key = f"shared-key-{timestamp}"

    # Create two separate tenants
    tenant1_email = f"tenant1-{timestamp}@example.com"
    tenant2_email = f"tenant2-{timestamp}@example.com"
    password = "securepass123"

    # Register tenant 1
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": tenant1_email,
            "password": password,
            "tenant_name": f"Tenant1-{timestamp}",
        },
    )
    token1_response = await client.post(
        "/api/v1/auth/token",
        json={"email": tenant1_email, "password": password},
    )
    token1 = token1_response.json()["access_token"]

    # Register tenant 2
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": tenant2_email,
            "password": password,
            "tenant_name": f"Tenant2-{timestamp}",
        },
    )
    token2_response = await client.post(
        "/api/v1/auth/token",
        json={"email": tenant2_email, "password": password},
    )
    token2 = token2_response.json()["access_token"]

    # Submit same idempotency key for both tenants
    job1_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": shared_idempotency_key,
            "filters": {},
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    job1_id = job1_response.json()["job_id"]

    job2_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": shared_idempotency_key,
            "filters": {},
        },
        headers={"Authorization": f"Bearer {token2}"},
    )
    job2_id = job2_response.json()["job_id"]

    # Verify both jobs were created with different IDs
    assert job1_id != job2_id
    assert job1_response.status_code == 201
    assert job2_response.status_code == 201
