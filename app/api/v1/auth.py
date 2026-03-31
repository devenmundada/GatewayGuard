"""
Authentication endpoints: register, login, refresh token.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token
from app.core.auth import verify_password, create_access_token, create_refresh_token, decode_token
import uuid

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if user exists
    existing_email = await crud.get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = await crud.get_user_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user
    user = await crud.create_user(
        db, 
        user_data.email, 
        user_data.username, 
        user_data.password
    )
    
    return user

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get access token."""
    # Get user by email
    user = await crud.get_user_by_email(db, user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "email": user.email})
    
    # Store refresh token in database
    await crud.create_refresh_token(db, user.id, refresh_token)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Get a new access token using a refresh token."""
    # Verify refresh token
    token_data = decode_token(refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if token exists in database and is valid
    stored_token = await crud.get_refresh_token(db, refresh_token)
    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found or expired"
        )
    
    # Get user
    user_id = int(token_data.get("sub"))
    user = await crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    new_access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "email": user.email})
    
    # Revoke old refresh token and store new one
    await crud.revoke_refresh_token(db, refresh_token)
    await crud.create_refresh_token(db, user.id, new_refresh_token)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )

@router.post("/logout")
async def logout(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Logout - revoke refresh token."""
    await crud.revoke_refresh_token(db, refresh_token)
    return {"message": "Successfully logged out"}
