"""
Database CRUD operations for users and tokens.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.db.models import RefreshToken, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback (used when Postgres is unreachable)
# ---------------------------------------------------------------------------
_MEM_USERS_BY_EMAIL: Dict[str, User] = {}
_MEM_USERS_BY_USERNAME: Dict[str, User] = {}
_MEM_REFRESH_TOKENS: Dict[str, RefreshToken] = {}

_MEM_NEXT_USER_ID = 1
_MEM_NEXT_REFRESH_TOKEN_ID = 1


def reset_memory_stores() -> None:
    """Reset in-memory stores between tests."""
    global _MEM_NEXT_USER_ID, _MEM_NEXT_REFRESH_TOKEN_ID
    _MEM_USERS_BY_EMAIL.clear()
    _MEM_USERS_BY_USERNAME.clear()
    _MEM_REFRESH_TOKENS.clear()
    _MEM_NEXT_USER_ID = 1
    _MEM_NEXT_REFRESH_TOKEN_ID = 1


def _should_fallback_to_memory(exc: BaseException) -> bool:
    """
    Determine whether the underlying DB is unreachable.

    We specifically treat connection/refusal errors as "use memory stores".
    """
    msg = str(exc).lower()
    return any(
        s in msg
        for s in (
            "connect call failed",
            "connection refused",
            "could not connect",
            "connection error",
        )
    )


async def _mem_get_user_by_email(email: str) -> User | None:
    return _MEM_USERS_BY_EMAIL.get(email.lower())


async def _mem_get_user_by_username(username: str) -> User | None:
    return _MEM_USERS_BY_USERNAME.get(username.lower())


async def _mem_get_user_by_id(user_id: int) -> User | None:
    for u in _MEM_USERS_BY_EMAIL.values():
        if u.id == user_id:
            return u
    return None


async def _mem_create_user(email: str, username: str, password: str) -> User:
    global _MEM_NEXT_USER_ID
    now = datetime.utcnow()
    hashed_password = get_password_hash(password)

    user = User(
        id=_MEM_NEXT_USER_ID,
        email=email.lower(),
        username=username,
        hashed_password=hashed_password,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    _MEM_NEXT_USER_ID += 1

    _MEM_USERS_BY_EMAIL[user.email] = user
    _MEM_USERS_BY_USERNAME[user.username.lower()] = user
    return user


async def _mem_create_refresh_token(user_id: int, token: str, expires_days: int) -> RefreshToken:
    global _MEM_NEXT_REFRESH_TOKEN_ID
    expires_at = datetime.utcnow() + timedelta(days=expires_days)
    refresh_token = RefreshToken(
        id=_MEM_NEXT_REFRESH_TOKEN_ID,
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        revoked=False,
        created_at=datetime.utcnow(),
    )
    _MEM_NEXT_REFRESH_TOKEN_ID += 1
    _MEM_REFRESH_TOKENS[token] = refresh_token
    return refresh_token


async def _mem_get_refresh_token(token: str) -> RefreshToken | None:
    rt = _MEM_REFRESH_TOKENS.get(token)
    if not rt or rt.revoked:
        return None
    if rt.expires_at <= datetime.utcnow():
        return None
    return rt


async def _mem_revoke_refresh_token(token: str) -> None:
    rt = _MEM_REFRESH_TOKENS.get(token)
    if rt:
        rt.revoked = True


# ---------------------------------------------------------------------------
# Public CRUD (try DB first; fall back to memory if DB is unreachable)
# ---------------------------------------------------------------------------
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    try:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    except BaseException as e:
        if _should_fallback_to_memory(e):
            return await _mem_get_user_by_email(email)
        raise


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    try:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    except BaseException as e:
        if _should_fallback_to_memory(e):
            return await _mem_get_user_by_username(username)
        raise


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except BaseException as e:
        if _should_fallback_to_memory(e):
            return await _mem_get_user_by_id(user_id)
        raise


async def create_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    try:
        hashed_password = get_password_hash(password)
        user = User(email=email, username=username, hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except BaseException as e:
        if _should_fallback_to_memory(e):
            logger.warning("DB unavailable; creating user in-memory: %s", email)
            return await _mem_create_user(email=email, username=username, password=password)
        raise


async def create_refresh_token(
    db: AsyncSession,
    user_id: int,
    token: str,
    expires_days: int = 7,
) -> RefreshToken:
    try:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        refresh_token = RefreshToken(token=token, user_id=user_id, expires_at=expires_at)
        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)
        return refresh_token
    except BaseException as e:
        if _should_fallback_to_memory(e):
            return await _mem_create_refresh_token(
                user_id=user_id, token=token, expires_days=expires_days
            )
        raise


async def get_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    try:
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()
    except BaseException as e:
        if _should_fallback_to_memory(e):
            return await _mem_get_refresh_token(token)
        raise


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    try:
        refresh_token = await get_refresh_token(db, token)
        if refresh_token:
            refresh_token.revoked = True
            await db.commit()
    except BaseException as e:
        if _should_fallback_to_memory(e):
            await _mem_revoke_refresh_token(token)
            return
        raise
def reset_memory_stores() -> None:
    """Reset in-memory stores between tests."""
    global _MEM_NEXT_USER_ID, _MEM_NEXT_REFRESH_TOKEN_ID
    _MEM_USERS_BY_EMAIL.clear()
    _MEM_USERS_BY_USERNAME.clear()
    _MEM_REFRESH_TOKENS.clear()
    _MEM_NEXT_USER_ID = 1
    _MEM_NEXT_REFRESH_TOKEN_ID = 1