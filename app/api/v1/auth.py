"""
Authentication endpoints: register, login, refresh, logout.
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.core.token_blacklist import revoke_access_token
from app.db import crud
from app.db.database import get_db
from app.schemas.auth import RefreshRequest, Token, UserCreate, UserLogin, UserResponse

router = APIRouter()

# Hash verified against when the email is unknown, so "no such user" and "wrong password"
# take the same time (otherwise response time reveals which emails are registered).
_DUMMY_HASH = (
    "$pbkdf2-sha256$29000$C4HQ2ntPifG.d641ZuwdQw$/zLasWriYD0PSNJlBX9Gas8F/Hdx5GMlWNZegLrjKgU"
)


def _issue_tokens(user) -> tuple[str, str]:
    claims = {"sub": str(user.id), "email": user.email}
    return create_access_token(data=claims), create_refresh_token(data=claims)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # One combined message: does not say which of email/username was the clash.
    taken = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email or username already registered",
    )
    if await crud.user_exists(db, user_data.email, user_data.username):
        raise taken
    try:
        return await crud.create_user(
            db, user_data.email, user_data.username, user_data.password
        )
    except crud.DuplicateUserError:
        raise taken from None  # lost a race with a concurrent registration


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get tokens."""
    user = await crud.get_user_by_email(db, user_data.email)
    password_ok = verify_password(
        user_data.password, user.hashed_password if user else _DUMMY_HASH
    )
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
        )

    access_token, refresh_token = _issue_tokens(user)
    await crud.create_refresh_token(db, user.id, refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new pair. The old refresh token stops working."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )
    token_data = decode_token(body.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise invalid
    if not await crud.get_refresh_token(db, body.refresh_token):
        raise invalid

    try:
        user_id = int(token_data["sub"])
    except (KeyError, ValueError):
        raise invalid from None
    user = await crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise invalid

    access_token, new_refresh_token = _issue_tokens(user)
    await crud.revoke_refresh_token(db, body.refresh_token)
    await crud.create_refresh_token(db, user.id, new_refresh_token)
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout")
async def logout(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Log out: revoke the refresh token and, if the current access token is supplied in the
    Authorization header, revoke that too (so it stops working immediately instead of
    after its 15 minute expiry).
    """
    await crud.revoke_refresh_token(db, body.refresh_token)

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = decode_token(auth_header[7:])
        if payload and payload.get("type") == "access" and payload.get("jti"):
            ttl = int(payload.get("exp", 0) - time.time())
            await revoke_access_token(payload["jti"], ttl)
    return {"message": "Successfully logged out"}
