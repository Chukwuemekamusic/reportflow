"""
Integration tests for user management API endpoints.

Run this test INSIDE the Docker container:
    docker compose exec api uv run pytest tests/integration/test_user_api.py -v

This test uses the real database running in Docker.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture(scope="function")
async def admin_auth(client: AsyncClient, unique_id: int):
    """Register a new tenant with admin user and return auth headers."""
    email = f"admin-{unique_id}@example.com"
    password = "adminpass123"
    tenant_name = f"AdminTenant-{unique_id}"

    # Register admin user
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
    assert user_data["role"] == "admin"

    # Login to get token
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_data["id"],
        "tenant_id": user_data["tenant_id"],
        "unique_id": unique_id,  # Pass through for tests that need additional unique data
    }


@pytest.mark.asyncio
async def test_create_user_as_admin(client: AsyncClient, admin_auth: dict):
    """Test that an admin can create a new user in their tenant."""
    headers = admin_auth["headers"]
    unique_id = admin_auth["unique_id"]
    email = f"newmember-{unique_id}@example.com"

    # Create a member user
    create_response = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "memberpass123",
            "role": "member",
        },
        headers=headers,
    )

    assert create_response.status_code == 201
    user_data = create_response.json()
    assert user_data["email"] == email
    assert user_data["role"] == "member"
    assert user_data["tenant_id"] == admin_auth["tenant_id"]
    assert user_data["is_active"] is True


@pytest.mark.asyncio
async def test_create_user_with_duplicate_email_in_same_tenant(
    client: AsyncClient, admin_auth: dict
):
    """Test that creating a user with duplicate email in same tenant fails."""
    headers = admin_auth["headers"]
    unique_id = admin_auth["unique_id"]
    email = f"duplicate-{unique_id}@example.com"

    # Create first user
    create_response1 = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "password123",
            "role": "member",
        },
        headers=headers,
    )
    assert create_response1.status_code == 201

    # Attempt to create second user with same email
    create_response2 = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "password456",
            "role": "member",
        },
        headers=headers,
    )
    assert create_response2.status_code == 409  # Conflict
    assert "already exists" in create_response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, admin_auth: dict):
    """Test that an admin can list users in their tenant."""
    headers = admin_auth["headers"]
    unique_id = admin_auth["unique_id"]

    # Create two users with unique emails
    await client.post(
        "/api/v1/users",
        json={
            "email": f"user1-{unique_id}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers=headers,
    )
    await client.post(
        "/api/v1/users",
        json={
            "email": f"user2-{unique_id}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers=headers,
    )

    # List users
    list_response = await client.get("/api/v1/users", headers=headers)

    assert list_response.status_code == 200
    data = list_response.json()
    assert "items" in data
    assert "total" in data
    # Should have at least 3 users: admin + 2 members
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_list_users_with_pagination(client: AsyncClient, admin_auth: dict):
    """Test user listing with pagination parameters."""
    headers = admin_auth["headers"]

    # List with limit and offset
    list_response = await client.get("/api/v1/users?limit=2&offset=0", headers=headers)

    assert list_response.status_code == 200
    data = list_response.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_deactivate_user_as_admin(client: AsyncClient, admin_auth: dict):
    """Test that an admin can deactivate a user."""
    headers = admin_auth["headers"]
    unique_id = admin_auth["unique_id"]

    # Create a user to deactivate (with unique email)
    create_response = await client.post(
        "/api/v1/users",
        json={
            "email": f"todeactivate-{unique_id}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    # Deactivate the user
    deactivate_response = await client.delete(
        f"/api/v1/users/{user_id}", headers=headers
    )

    assert deactivate_response.status_code == 200
    user_data = deactivate_response.json()
    assert user_data["is_active"] is False
    assert user_data["id"] == user_id


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client: AsyncClient, admin_auth: dict):
    """Test that an admin cannot deactivate their own account."""
    headers = admin_auth["headers"]
    admin_user_id = admin_auth["user_id"]

    # Attempt to deactivate self
    deactivate_response = await client.delete(
        f"/api/v1/users/{admin_user_id}", headers=headers
    )

    assert deactivate_response.status_code == 400  # Bad Request
    assert "cannot deactivate" in deactivate_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivate_nonexistent_user(client: AsyncClient, admin_auth: dict):
    """Test that deactivating a non-existent user returns 404."""
    headers = admin_auth["headers"]
    fake_user_id = "00000000-0000-0000-0000-000000000000"

    deactivate_response = await client.delete(
        f"/api/v1/users/{fake_user_id}", headers=headers
    )

    assert deactivate_response.status_code == 404
    assert "not found" in deactivate_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_user_requires_admin_role(client: AsyncClient, admin_auth: dict):
    """Test that non-admin users cannot create users."""
    admin_headers = admin_auth["headers"]
    unique_id = admin_auth["unique_id"]

    # Create a member user (with unique email)
    member_email = f"member-{unique_id}@example.com"
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

    # Login as the member
    token_response = await client.post(
        "/api/v1/auth/token",
        json={"email": member_email, "password": "memberpass123"},
    )
    member_token = token_response.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Try to create a user as member (should fail)
    create_as_member_response = await client.post(
        "/api/v1/users",
        json={
            "email": f"another-{unique_id}@example.com",
            "password": "password123",
            "role": "member",
        },
        headers=member_headers,
    )

    assert create_as_member_response.status_code == 403  # Forbidden
    assert "admin" in create_as_member_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_users_are_isolated_by_tenant(client: AsyncClient, unique_id: int):
    """Test that users can only see users in their own tenant."""
    # Create two separate tenants with admin users

    # Tenant 1
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admin1-{unique_id}@example.com",
            "password": "password123",
            "tenant_name": f"Tenant1-{unique_id}",
        },
    )
    token1_response = await client.post(
        "/api/v1/auth/token",
        json={"email": f"admin1-{unique_id}@example.com", "password": "password123"},
    )
    token1 = token1_response.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Tenant 2
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admin2-{unique_id}@example.com",
            "password": "password123",
            "tenant_name": f"Tenant2-{unique_id}",
        },
    )
    token2_response = await client.post(
        "/api/v1/auth/token",
        json={"email": f"admin2-{unique_id}@example.com", "password": "password123"},
    )
    token2 = token2_response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Create users in each tenant (using unique_id for uniqueness)
    tenant1_user_email = f"tenant1user-{unique_id}@example.com"
    tenant2_user_email = f"tenant2user-{unique_id}@example.com"

    await client.post(
        "/api/v1/users",
        json={"email": tenant1_user_email, "password": "password123", "role": "member"},
        headers=headers1,
    )
    await client.post(
        "/api/v1/users",
        json={"email": tenant2_user_email, "password": "password123", "role": "member"},
        headers=headers2,
    )

    # List users from each tenant
    list1 = await client.get("/api/v1/users", headers=headers1)
    list2 = await client.get("/api/v1/users", headers=headers2)

    users1_emails = [u["email"] for u in list1.json()["items"]]
    users2_emails = [u["email"] for u in list2.json()["items"]]

    # Each tenant should only see their own users
    assert tenant1_user_email in users1_emails
    assert tenant2_user_email not in users1_emails

    assert tenant2_user_email in users2_emails
    assert tenant1_user_email not in users2_emails
