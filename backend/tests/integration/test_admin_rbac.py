"""
Integration tests for admin RBAC (Role-Based Access Control).

Tests the security fix for cross-tenant data leakage in admin endpoints.

Run this test INSIDE the Docker container:
    docker compose exec api bash -c "PYTHONPATH=/app uv run pytest tests/integration/test_admin_rbac.py -v"
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime


@pytest_asyncio.fixture(scope="function")
async def tenant_admin_auth(client: AsyncClient, unique_id: int):
    """Create a tenant admin user and return auth headers."""
    email = f"tenant-admin-{unique_id}@example.com"
    password = "adminpass123"
    tenant_name = f"TenantCorp-{unique_id}"

    # Register (creates tenant + admin user)
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": tenant_name,
        },
    )
    assert register_response.status_code == 201
    user_data = register_response.json()
    assert user_data["role"] == "admin"  # Tenant admin

    # Login
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    token = token_response.json()["access_token"]

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_data["id"],
        "tenant_id": user_data["tenant_id"],
        "email": email,
        "unique_id": unique_id,
    }


@pytest.mark.asyncio
async def test_tenant_admin_cannot_access_system_admin_endpoints(
    client: AsyncClient, tenant_admin_auth: dict
):
    """Test that tenant admins (role='admin') cannot access /admin/* endpoints."""
    headers = tenant_admin_auth["headers"]

    # Try to access system admin endpoints
    endpoints_to_test = [
        "/api/v1/admin/jobs",
        "/api/v1/admin/dlq",
        "/api/v1/admin/tenants",
        "/api/v1/admin/queue",
    ]

    for endpoint in endpoints_to_test:
        response = await client.get(endpoint, headers=headers)
        assert response.status_code == 403, f"Tenant admin should not access {endpoint}"
        assert "system administrator" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tenant_admin_can_access_tenant_endpoints(
    client: AsyncClient, tenant_admin_auth: dict
):
    """Test that tenant admins CAN access /tenant/* endpoints."""
    headers = tenant_admin_auth["headers"]

    # These should succeed (200 OK)
    endpoints_to_test = [
        "/api/v1/tenant/jobs",
        "/api/v1/tenant/dlq",
        "/api/v1/tenant/stats",
    ]

    for endpoint in endpoints_to_test:
        response = await client.get(endpoint, headers=headers)
        assert response.status_code == 200, f"Tenant admin should access {endpoint}"


@pytest.mark.asyncio
async def test_tenant_jobs_endpoint_filters_by_tenant(client: AsyncClient):
    """
    Test that /tenant/jobs only returns jobs from the current tenant.
    Create 2 tenants, submit jobs from each, verify isolation.
    """
    timestamp = int(datetime.now().timestamp())

    # Tenant 1
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admin1-{timestamp}@test.com",
            "password": "password123",
            "tenant_name": f"Tenant1-{timestamp}",
        },
    )
    token1_response = await client.post(
        "/api/v1/auth/token",
        json={"email": f"admin1-{timestamp}@test.com", "password": "password123"},
    )
    token1 = token1_response.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Tenant 2
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admin2-{timestamp}@test.com",
            "password": "password123",
            "tenant_name": f"Tenant2-{timestamp}",
        },
    )
    token2_response = await client.post(
        "/api/v1/auth/token",
        json={"email": f"admin2-{timestamp}@test.com", "password": "password123"},
    )
    token2 = token2_response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Submit job from Tenant 1
    job1_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "sales_summary",
            "priority": 5,
            "idempotency_key": f"tenant1-{timestamp}",
        },
        headers=headers1,
    )
    assert job1_response.status_code == 201
    job1_id = job1_response.json()["job_id"]

    # Submit job from Tenant 2
    job2_response = await client.post(
        "/api/v1/reports",
        json={
            "report_type": "csv_export",
            "priority": 5,
            "idempotency_key": f"tenant2-{timestamp}",
        },
        headers=headers2,
    )
    assert job2_response.status_code == 201
    job2_id = job2_response.json()["job_id"]

    # Tenant 1 admin lists jobs - should only see job1
    tenant1_jobs = await client.get("/api/v1/tenant/jobs", headers=headers1)
    assert tenant1_jobs.status_code == 200
    tenant1_job_ids = [j["job_id"] for j in tenant1_jobs.json()["jobs"]]
    assert job1_id in tenant1_job_ids
    assert job2_id not in tenant1_job_ids  # ✅ Cross-tenant isolation

    # Tenant 2 admin lists jobs - should only see job2
    tenant2_jobs = await client.get("/api/v1/tenant/jobs", headers=headers2)
    assert tenant2_jobs.status_code == 200
    tenant2_job_ids = [j["job_id"] for j in tenant2_jobs.json()["jobs"]]
    assert job2_id in tenant2_job_ids
    assert job1_id not in tenant2_job_ids  # ✅ Cross-tenant isolation


@pytest.mark.asyncio
async def test_tenant_stats_endpoint_is_tenant_scoped(
    client: AsyncClient, tenant_admin_auth: dict
):
    """Test that /tenant/stats only shows stats for the current tenant."""
    headers = tenant_admin_auth["headers"]
    tenant_id = tenant_admin_auth["tenant_id"]

    # Get tenant stats
    response = await client.get("/api/v1/tenant/stats", headers=headers)
    assert response.status_code == 200

    stats = response.json()
    assert stats["tenant_id"] == tenant_id
    assert "total_jobs" in stats
    assert "jobs_by_status" in stats
    assert "unresolved_dlq_entries" in stats


@pytest.mark.asyncio
async def test_member_user_cannot_access_tenant_admin_endpoints(
    client: AsyncClient, tenant_admin_auth: dict
):
    """Test that regular users (role='member') cannot access /tenant/* endpoints."""
    admin_headers = tenant_admin_auth["headers"]
    timestamp = int(datetime.now().timestamp())

    # Create a member user (with unique email)
    member_email = f"member-{timestamp}@test.com"
    create_response = await client.post(
        "/api/v1/users",
        json={
            "email": member_email,
            "password": "memberpass123",
            "role": "member",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 201

    # Login as member
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": member_email, "password": "memberpass123"},
    )
    member_token = token_response.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Try to access tenant admin endpoints
    response = await client.get("/api/v1/tenant/jobs", headers=member_headers)
    assert response.status_code == 403  # Forbidden
    assert "admin" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_any_admin_endpoints(client: AsyncClient):
    """Test that unauthenticated requests get 401."""
    endpoints = [
        "/api/v1/admin/jobs",
        "/api/v1/admin/tenants",
        "/api/v1/tenant/jobs",
        "/api/v1/tenant/stats",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 401, f"Should require auth for {endpoint}"
