from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import uuid

import pytest

from app.services.user_service import (
    EmailAlreadyExistsInTenantError,
    UserNotFoundError,
    CannotDeactivateSelfError,
    create_user_in_tenant,
    list_tenant_users,
    deactivate_user,
)
from app.schemas.user import UserCreateRequest


@pytest.mark.asyncio
async def test_create_user_raises_when_email_exists_in_tenant() -> None:
    """Test that creating a user with an existing email in the same tenant raises an error."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, role="admin")

    # Mock existing user with same email in the tenant
    existing_user = SimpleNamespace(id=uuid.uuid4())
    result = Mock()
    result.scalar_one_or_none.return_value = existing_user
    db.execute.return_value = result

    payload = UserCreateRequest(
        email="exists@example.com",
        password="password123",
        role="member"
    )

    with pytest.raises(EmailAlreadyExistsInTenantError):
        await create_user_in_tenant(db, admin_user, payload)


@pytest.mark.asyncio
async def test_create_user_in_tenant_creates_user_with_correct_role() -> None:
    """Test that a new user is created with the specified role in the admin's tenant."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, role="admin")

    # Mock no existing user
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    payload = UserCreateRequest(
        email="newmember@example.com",
        password="password123",
        role="member"
    )

    with patch("app.services.user_service.hash_password", return_value="hashed-password"):
        await create_user_in_tenant(db, admin_user, payload)

    # Verify user was added to database
    assert db.add.call_count == 1
    created_user = db.add.call_args.args[0]

    assert created_user.tenant_id == tenant_id
    assert created_user.email == payload.email
    assert created_user.hashed_password == "hashed-password"
    assert created_user.role == "member"
    assert db.flush.await_count == 1
    assert db.refresh.await_count == 1


@pytest.mark.asyncio
async def test_create_user_in_tenant_can_create_admin() -> None:
    """Test that an admin can create another admin user."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, role="admin")

    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    payload = UserCreateRequest(
        email="newadmin@example.com",
        password="password123",
        role="admin"
    )

    with patch("app.services.user_service.hash_password", return_value="hashed-password"):
        await create_user_in_tenant(db, admin_user, payload)

    created_user = db.add.call_args.args[0]
    assert created_user.role == "admin"


@pytest.mark.asyncio
async def test_list_tenant_users_returns_users_and_count() -> None:
    """Test that list_tenant_users returns paginated users and total count."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id, role="admin")

    # Mock count query
    count_result = Mock()
    count_result.scalar.return_value = 5

    # Mock users query
    user1 = SimpleNamespace(id=uuid.uuid4(), email="user1@example.com")
    user2 = SimpleNamespace(id=uuid.uuid4(), email="user2@example.com")
    users_result = Mock()
    users_result.scalars.return_value.all.return_value = [user1, user2]

    # Configure db.execute to return different results for count and select queries
    db.execute.side_effect = [count_result, users_result]

    users, total = await list_tenant_users(db, admin_user, limit=2, offset=0)

    assert total == 5
    assert len(users) == 2
    assert users[0].email == "user1@example.com"
    assert users[1].email == "user2@example.com"


@pytest.mark.asyncio
async def test_deactivate_user_raises_when_deactivating_self() -> None:
    """Test that an admin cannot deactivate their own account."""
    db = AsyncMock()
    admin_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=admin_id, tenant_id=tenant_id, role="admin")

    with pytest.raises(CannotDeactivateSelfError):
        await deactivate_user(db, admin_user, admin_id)


@pytest.mark.asyncio
async def test_deactivate_user_raises_when_user_not_found() -> None:
    """Test that deactivating a non-existent user raises an error."""
    db = AsyncMock()
    admin_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=admin_id, tenant_id=tenant_id, role="admin")

    # Mock user not found
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(UserNotFoundError):
        await deactivate_user(db, admin_user, uuid.uuid4())


@pytest.mark.asyncio
async def test_deactivate_user_sets_is_active_to_false() -> None:
    """Test that deactivating a user sets is_active=False."""
    db = AsyncMock()
    admin_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    admin_user = SimpleNamespace(id=admin_id, tenant_id=tenant_id, role="admin")

    # Mock user found
    target_user = SimpleNamespace(id=user_id, is_active=True, tenant_id=tenant_id)
    result = Mock()
    result.scalar_one_or_none.return_value = target_user
    db.execute.return_value = result

    deactivated_user = await deactivate_user(db, admin_user, user_id)

    assert target_user.is_active is False
    assert db.flush.await_count == 1
    assert db.refresh.await_count == 1
    assert deactivated_user is target_user
