"""
FastAPI dependencies for dependency injection.
Currently re-exports database session dependency from db.base
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from app.db.base import get_db
from app.db.models.user import User
from app.core.security import decode_access_token

# Tells FastAPI where to find the token (used for Swagger UI "Authorize" button)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency — yields the current user from the JWT token.
    Raises 401 if the token is invalid or the user is not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency — yields the current user if they are an admin or system_admin.
    Raises 403 if the user is not an admin.

    Use this for tenant-scoped admin operations (user management, tenant settings).
    For system-wide operations, use require_system_admin() instead.
    """
    if current_user.role not in ("admin", "system_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

async def require_admin(
    current_user: User = Depends(get_current_admin)
) -> bool:
    """
    FastAPI dependency — yields True if the current user is an admin or system_admin.
    Raises 403 if the user is not an admin.

    Use this for tenant-scoped admin operations.
    """
    return True

async def require_system_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency — yields the current user ONLY if they are a system_admin.
    Raises 403 if the user is not a system admin.

    Use this for platform-wide operations that should only be accessible to
    platform operators (viewing all tenants, system-wide metrics, etc.).

    Regular tenant admins (role='admin') will receive 403 Forbidden.
    """
    if current_user.role != "system_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administrator access required"
        )
    return current_user

__all__ = ["get_db", "get_current_user", "get_current_admin", "require_admin", "require_system_admin"]
