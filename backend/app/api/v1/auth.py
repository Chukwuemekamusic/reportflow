from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_db
from app.core.utils import create_slug
from app.db.models.user import User
from app.db.models.tenant import Tenant
from app.core.security import hash_password, create_access_token, verify_password
from app.core.config import get_settings
from app.schemas.auth import RegisterRequest, TokenRequest, TokenResponse, UserResponse

router = APIRouter()

settings = get_settings()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, 
    db: AsyncSession = Depends(get_db)
):
    # Check if email already exists 
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    
    # create tenant
    tenant = Tenant(name=payload.tenant_name, slug=create_slug(payload.tenant_name))
    db.add(tenant)
    await db.flush()
    
    # Create user
    user = User(
        tenant_id=tenant.id, 
        email=payload.email, 
        hashed_password=hash_password(payload.password),
        role="admin"
    )
    db.add(user)
    await db.flush()
    return user 

@router.post("/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login_for_access_token(
    payload: TokenRequest, 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
    
    access_token = create_access_token(data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role})
    return TokenResponse(access_token=access_token, expires_in=settings.jwt_expire_minutes * 60)
    