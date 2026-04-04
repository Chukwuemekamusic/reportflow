"""Integration tests for auth endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_creates_tenant_and_user(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "password123",
        "tenant_name": "New Corp",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "admin"  # first user in tenant is admin
    assert "tenant_id" in data
    assert "hashed_password" not in data  # never leak this


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "password123", "tenant_name": "Corp A"}
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_jwt(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com", "password": "password123", "tenant_name": "Login Corp"
    })
    res = await client.post("/api/v1/auth/token", json={
        "email": "login@example.com", "password": "password123"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_wrong_password_returns_401(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "auth@example.com", "password": "correct", "tenant_name": "Corp"
    })
    res = await client.post("/api/v1/auth/token", json={
        "email": "auth@example.com", "password": "wrong"
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_no_token(client: AsyncClient):
    res = await client.get("/api/v1/reports")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_bad_token(client: AsyncClient):
    res = await client.get("/api/v1/reports", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401