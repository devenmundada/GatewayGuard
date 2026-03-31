"""
Pydantic schemas for authentication.
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema for user response (excludes password)."""
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for token payload."""
    user_id: Optional[int] = None
    email: Optional[str] = None
