"""
User management service for admin operations within a tenant.
Handles creating, listing, and deactivating users.
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.db.models.user import User
from app.schemas.user import UserCreateRequest
import uuid


class UserServiceError(Exception):
    """Base exception for user service errors."""


class EmailAlreadyExistsInTenantError(UserServiceError):
    def __init__(self) -> None:
        super().__init__("Email already exists in this tenant")


class UserNotFoundError(UserServiceError):
    def __init__(self) -> None:
        super().__init__("User not found")


class CannotDeactivateSelfError(UserServiceError):
    def __init__(self) -> None:
        super().__init__("Cannot deactivate your own account")


async def create_user_in_tenant(
    db: AsyncSession,
    admin_user: User,
    payload: UserCreateRequest,
) -> User:
    """
    Create a new user within the admin's tenant.

    Args:
        db: Database session
        admin_user: The admin user creating the new user (provides tenant_id)
        payload: User creation data (email, password, role)

    Returns:
        The newly created User instance

    Raises:
        EmailAlreadyExistsInTenantError: If email already exists in the tenant
    """
    # Check if email already exists in this tenant
    result = await db.execute(
        select(User).where(
            User.tenant_id == admin_user.tenant_id, User.email == payload.email
        )
    )
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise EmailAlreadyExistsInTenantError()

    # Create new user in the admin's tenant
    user = User(
        tenant_id=admin_user.tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def list_tenant_users(
    db: AsyncSession,
    admin_user: User,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    """
    List all users in the admin's tenant with pagination.

    Args:
        db: Database session
        admin_user: The admin user (provides tenant_id for scoping)
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        Tuple of (list of users, total count)
    """
    # Get total count
    count_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == admin_user.tenant_id)
    )
    total = count_result.scalar() or 0

    # Get paginated users
    result = await db.execute(
        select(User)
        .where(User.tenant_id == admin_user.tenant_id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = list(result.scalars().all())

    return users, total


async def deactivate_user(
    db: AsyncSession,
    admin_user: User,
    user_id: uuid.UUID,
) -> User:
    """
    Soft-delete a user by setting is_active=False.

    Args:
        db: Database session
        admin_user: The admin performing the deactivation
        user_id: ID of the user to deactivate

    Returns:
        The deactivated User instance

    Raises:
        UserNotFoundError: If user doesn't exist in the tenant
        CannotDeactivateSelfError: If admin tries to deactivate themselves
    """
    # Prevent self-deactivation
    if admin_user.id == user_id:
        raise CannotDeactivateSelfError()

    # Get user from same tenant
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == admin_user.tenant_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundError()

    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return user
