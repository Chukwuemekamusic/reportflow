"""
Simplified integration test using the existing Docker database.

Run this test INSIDE the Docker container:
    docker compose exec api uv run pytest tests/integration/test_full_flow.py -v

This test uses the real database, Redis, and Celery workers running in Docker.
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.main import app


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Create an async HTTP client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_full_report_generation_flow(async_client: AsyncClient):
    """
    Test the complete end-to-end flow from user registration to report download.
    Uses the real Docker database, Celery workers, and MinIO.
    """
    timestamp = int(datetime.now().timestamp())
    email = f"test-{timestamp}@example.com"
    password = "securepass123"
    tenant_name = f"TestCorp-{timestamp}"

    # ────────────────────────────────────────────────────────────
    # Step 1: Register a new user/tenant
    # ────────────────────────────────────────────────────────────
    register_response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": tenant_name,
        },
    )
    assert register_response.status_code == 201
    user_data = register_response.json()
    assert user_data["email"] == email
    assert user_data["role"] == "admin"
    user_id = user_data["id"]

    # ────────────────────────────────────────────────────────────
    # Step 2: Login and obtain JWT token
    # ────────────────────────────────────────────────────────────
    token_response = await async_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    assert token_response.status_code == 200
    token_data = token_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # ────────────────────────────────────────────────────────────
    # Step 3: Submit a sales_summary report
    # ────────────────────────────────────────────────────────────
    idempotency_key = f"test-job-{timestamp}"
    submit_response = await async_client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {"region": "EMEA", "status": "active"},
        },
        headers=headers,
    )
    assert submit_response.status_code == 201
    job_data = submit_response.json()
    assert job_data["report_type"] == "sales_summary"
    assert job_data["status"] in ("queued", "running")
    job_id = job_data["job_id"]

    # ────────────────────────────────────────────────────────────
    # Step 4: Test idempotency - resubmit with same key
    # ────────────────────────────────────────────────────────────
    resubmit_response = await async_client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": idempotency_key,
            "filters": {"region": "EMEA", "status": "active"},
        },
        headers=headers,
    )
    # Should return 200 (not 201) with the same job
    assert resubmit_response.status_code == 200
    resubmit_data = resubmit_response.json()
    assert resubmit_data["job_id"] == job_id

    # ────────────────────────────────────────────────────────────
    # Step 5: Poll for job completion (max 60 seconds)
    # ────────────────────────────────────────────────────────────
    max_attempts = 30
    for attempt in range(max_attempts):
        status_response = await async_client.get(
            f"/api/v1/reports/{job_id}",
            headers=headers,
        )
        assert status_response.status_code == 200
        status_data = status_response.json()

        if status_data["status"] == "completed":
            assert status_data["progress"] == 100
            assert status_data["links"]["download"] is not None
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Job failed: {status_data.get('error_message')}")

        await asyncio.sleep(2)
    else:
        pytest.fail("Job did not complete within timeout (60s)")

    # ────────────────────────────────────────────────────────────
    # Step 6: Download the report (presigned URL redirect)
    # ────────────────────────────────────────────────────────────
    download_response = await async_client.get(
        f"/api/v1/reports/{job_id}/download",
        headers=headers,
        follow_redirects=False,  # Check that we get a 302 redirect
    )
    assert download_response.status_code == 302
    redirect_url = download_response.headers.get("location")
    assert redirect_url is not None
    assert "reportflow-files" in redirect_url  # MinIO bucket name
    assert job_id in redirect_url  # Job ID in object key

    # ────────────────────────────────────────────────────────────
    # Step 7: List jobs and verify the job appears
    # ────────────────────────────────────────────────────────────
    list_response = await async_client.get(
        "/api/v1/reports",
        headers=headers,
    )
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total"] >= 1
    job_ids = [job["job_id"] for job in list_data["items"]]
    assert job_id in job_ids

    # ────────────────────────────────────────────────────────────
    # Step 8: Filter jobs by status
    # ────────────────────────────────────────────────────────────
    filter_response = await async_client.get(
        "/api/v1/reports?status=completed&report_type=sales_summary",
        headers=headers,
    )
    assert filter_response.status_code == 200
    filter_data = filter_response.json()
    assert all(job["status"] == "completed" for job in filter_data["items"])
    assert all(job["report_type"] == "sales_summary" for job in filter_data["items"])


@pytest.mark.skip(reason="Event loop conflict - covered by manual testing")
@pytest.mark.asyncio
async def test_download_incomplete_job_fails(async_client: AsyncClient):
    """
    Test that attempting to download a non-completed job returns 409.
    """
    timestamp = int(datetime.now().timestamp())
    email = f"download-test-{timestamp}@example.com"
    password = "securepass123"

    # Register and login
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": f"DownloadTest-{timestamp}",
        },
    )
    token_response = await async_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Submit job
    submit_response = await async_client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "filters": {},
        },
        headers=headers,
    )
    job_id = submit_response.json()["job_id"]

    # Immediately try to download (job is likely still queued/running)
    download_response = await async_client.get(
        f"/api/v1/reports/{job_id}/download",
        headers=headers,
        follow_redirects=False,
    )

    # Should get 409 Conflict if job is not completed
    if download_response.status_code != 302:  # If not already completed
        assert download_response.status_code == 409
        error_data = download_response.json()
        assert "not ready" in error_data["detail"].lower()
