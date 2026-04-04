"""
User management API endpoints (admin-only).
Allows tenant admins to invite/manage users within their tenant.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_admin
from app.db.models.user import User
from app.schemas.user import UserCreateRequest, UserResponse, UserListResponse
from app.services import user_service
from app.services.user_service import (
    EmailAlreadyExistsInTenantError,
    UserNotFoundError,
    CannotDeactivateSelfError,
)
import uuid


router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user in the current tenant (admin-only)",
)
async def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user within the admin's tenant.

    Only admins can create users. The new user will be created in the same
    tenant as the admin making the request.

    - **email**: Must be unique within the tenant
    - **password**: Minimum 8 characters
    - **role**: Either "member" or "admin"
    """
    try:
        user = await user_service.create_user_in_tenant(db, current_user, payload)
        await db.commit()
        return user
    except EmailAlreadyExistsInTenantError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=UserListResponse,
    summary="List all users in the current tenant (admin-only)",
)
async def list_users(
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of users to return"
    ),
    offset: int = Query(0, ge=0, description="Number of users to skip"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all users in the admin's tenant with pagination.

    Returns users ordered by creation date (newest first).
    """
    users, total = await user_service.list_tenant_users(db, current_user, limit, offset)
    return UserListResponse(
        items=users,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{user_id}", response_model=UserResponse, summary="Deactivate a user (admin-only)"
)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete a user by setting is_active=False.

    The user will no longer be able to log in, but their data is preserved.
    Admins cannot deactivate their own account.
    """
    try:
        user = await user_service.deactivate_user(db, current_user, user_id)
        await db.commit()
        return user
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CannotDeactivateSelfError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
