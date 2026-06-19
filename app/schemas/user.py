from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    is_admin: bool = False

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_admin: bool
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"