from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core.utils import create_slug
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.schemas.auth import RegisterRequest, TokenRequest, TokenResponse


settings = get_settings()


class AuthServiceError(Exception):
    """Base exception for auth service errors."""


class EmailAlreadyExistsError(AuthServiceError):
    def __init__(self) -> None:
        super().__init__("Email already exists")


class InvalidCredentialsError(AuthServiceError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InactiveUserError(AuthServiceError):
    def __init__(self) -> None:
        super().__init__("User is not active")


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    existing_user = result.scalar_one_or_none()
    if existing_user is not None:
        raise EmailAlreadyExistsError()

    tenant = Tenant(name=payload.tenant_name, slug=create_slug(payload.tenant_name))
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, payload: TokenRequest) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InactiveUserError()

    return user


def create_token_response(user: User) -> TokenResponse:
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
        }
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )