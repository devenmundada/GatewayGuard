"""
Pydantic schemas for authentication.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    # max_length bounds the cost of password hashing (a 1 MB "password" is a DoS).
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str = Field(..., max_length=128)


class UserResponse(BaseModel):
    """Schema for user response (excludes password)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body for /refresh and /logout (tokens never travel in URLs: URLs end up in logs)."""
    refresh_token: str = Field(..., min_length=10, max_length=2048)


class TokenData(BaseModel):
    """Schema for token payload."""
    user_id: int | None = None
    email: str | None = None
