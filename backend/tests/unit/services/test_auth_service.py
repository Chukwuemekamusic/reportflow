from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.auth_service import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    authenticate_user,
    create_token_response,
    register_user,
)
from app.schemas.auth import RegisterRequest, TokenRequest


@pytest.mark.asyncio
async def test_register_user_raises_when_email_exists() -> None:
    db = AsyncMock()
    existing_user = SimpleNamespace(id="user-1")
    result = Mock()
    result.scalar_one_or_none.return_value = existing_user
    db.execute.return_value = result

    payload = RegisterRequest(
        email="exists@example.com",
        password="secret123",
        tenant_name="Acme",
    )

    with pytest.raises(EmailAlreadyExistsError):
        await register_user(db, payload)


@pytest.mark.asyncio
async def test_register_user_creates_tenant_and_admin_user() -> None:
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    payload = RegisterRequest(
        email="new@example.com",
        password="secret123",
        tenant_name="Acme Corporation",
    )

    with patch("app.services.auth_service.hash_password", return_value="hashed-password"):
        user = await register_user(db, payload)

    assert db.add.call_count == 2
    tenant = db.add.call_args_list[0].args[0]
    created_user = db.add.call_args_list[1].args[0]

    assert tenant.name == "Acme Corporation"
    assert tenant.slug == "acme-corporation"
    assert created_user.email == payload.email
    assert created_user.hashed_password == "hashed-password"
    assert created_user.role == "admin"
    assert db.flush.await_count == 2
    assert user is created_user


@pytest.mark.asyncio
async def test_authenticate_user_raises_for_invalid_credentials() -> None:
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    payload = TokenRequest(email="missing@example.com", password="badpass")

    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(db, payload)


@pytest.mark.asyncio
async def test_authenticate_user_raises_for_inactive_user() -> None:
    db = AsyncMock()
    user = SimpleNamespace(
        hashed_password="stored-hash",
        is_active=False,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result

    payload = TokenRequest(email="user@example.com", password="secret123")

    with patch("app.services.auth_service.verify_password", return_value=True):
        with pytest.raises(InactiveUserError):
            await authenticate_user(db, payload)


def test_create_token_response_uses_expected_payload() -> None:
    user = SimpleNamespace(
        id="user-id",
        tenant_id="tenant-id",
        role="admin",
    )

    with patch("app.services.auth_service.create_access_token", return_value="signed-token") as mock_create_token:
        response = create_token_response(user)

    assert response.access_token == "signed-token"
    assert response.expires_in == 3600
    mock_create_token.assert_called_once_with(
        data={"sub": "user-id", "tenant_id": "tenant-id", "role": "admin"}
    )