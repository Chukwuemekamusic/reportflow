from pydantic import BaseModel, EmailStr
import uuid

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str        # creates a new tenant for the user
    
class TokenRequest(BaseModel):
    email: EmailStr
    password: str
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int         # seconds
    
class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    tenant_id: uuid.UUID
    
# class RegisterResponse(BaseModel):
#     user_id: uuid.UUID
#     tenant_id: uuid.UUID
#     access_token: str
#     token_type: str = "bearer" 