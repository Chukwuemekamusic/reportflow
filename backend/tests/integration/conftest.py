"""
Integration test fixtures for Docker environment.

These tests run INSIDE the Docker container using the real PostgreSQL/Redis services.
Tests use timestamp-based isolation (no transactional rollback).

Run with:
    docker compose exec api uv run pytest tests/integration/ -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from app.main import create_app
from app.db.base import engine


@pytest.fixture(scope="function")
def unique_id():
    """
    Generate unique ID for test data isolation.

    Uses millisecond precision to ensure uniqueness even when tests run in quick succession.
    Use this in email addresses, tenant names, etc. to prevent data collisions.

    Example:
        email = f"admin-{unique_id}@example.com"
        tenant_name = f"TestTenant-{unique_id}"
    """
    return int(datetime.now().timestamp() * 1000)


@pytest_asyncio.fixture(scope="function")
async def client():
    """
    AsyncClient for making HTTP requests to the FastAPI app.

    Creates a FRESH app instance per test to avoid async event loop conflicts.
    The app's lifespan context (which spawns background tasks) is properly
    managed within each test's event loop.

    Uses the production database connection (no override).
    Tests rely on timestamps for data isolation.

    IMPORTANT: Disposes the SQLAlchemy engine's connection pool after each test
    to prevent "attached to a different loop" errors with asyncpg connections.
    """
    app = create_app()
    transport = ASGITransport(app=app, raise_app_exceptions=True)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # AsyncClient.__aexit__ will trigger app lifespan shutdown automatically

    # Dispose the connection pool to prevent event loop conflicts
    # This forces SQLAlchemy to create fresh connections in the next test's event loop
    await engine.dispose()
