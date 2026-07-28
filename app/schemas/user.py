from app.models.enumerators.enumerators import UserRole
from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.user  # todo modificare, non va fatto qui


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    role: UserRole
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefreshRequest(BaseModel):
    refresh_token: str