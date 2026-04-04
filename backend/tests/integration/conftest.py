"""
Integration test fixtures for Docker environment.

These tests run INSIDE the Docker container using the real PostgreSQL/Redis services.
Tests use timestamp-based isolation (no transactional rollback).

Run with:
    docker compose exec api uv run pytest tests/integration/ -v
"""
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def client():
    """
    AsyncClient for making HTTP requests to the FastAPI app.

    Uses the production database connection (no override).
    Tests rely on timestamps for data isolation.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
