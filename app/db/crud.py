"""
Database CRUD operations for users, refresh tokens and tasks.

There is deliberately NO in-memory fallback here. If PostgreSQL is unreachable the
exception propagates and the API answers 503 (see main.py). The previous fallback
created accounts in one worker's memory (lost on restart, invisible to the other
three workers) and made valid logins fail with a misleading 401.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.db.models import RefreshToken, Task, User, utc_now


class DuplicateUserError(Exception):
    """Email or username already taken (also raised when a race hits the unique index)."""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def user_exists(db: AsyncSession, email: str, username: str) -> bool:
    result = await db.execute(
        select(User.id)
        .where(or_(User.email == email.lower(), User.username == username))
        .limit(1)
    )
    return result.first() is not None


async def create_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    user = User(
        email=email.lower(),
        username=username,
        hashed_password=get_password_hash(password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateUserError from exc
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Refresh tokens (stored hashed)
# ---------------------------------------------------------------------------
async def create_refresh_token(
    db: AsyncSession, user_id: int, token: str, expires_days: int = 7
) -> RefreshToken:
    row = RefreshToken(
        token_hash=hash_token(token),
        user_id=user_id,
        expires_at=utc_now() + timedelta(days=expires_days),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(token),
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > utc_now(),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
    """Revoke a token. Returns True if a live token was revoked."""
    row = await get_refresh_token(db, token)
    if row is None:
        return False
    row.revoked = True
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Tasks (every query is scoped to the owner: users can never see each other's tasks)
# ---------------------------------------------------------------------------
async def create_task(
    db: AsyncSession, user_id: int, title: str, description: str | None
) -> Task:
    task = Task(user_id=user_id, title=title, description=description)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(
    db: AsyncSession,
    user_id: int,
    completed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Task]:
    query = select(Task).where(Task.user_id == user_id)
    if completed is not None:
        query = query.where(Task.completed.is_(completed))
    query = query.order_by(Task.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def get_task(db: AsyncSession, user_id: int, task_id: int) -> Task | None:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_task(db: AsyncSession, task: Task, changes: dict) -> Task:
    for field, value in changes.items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task: Task) -> None:
    await db.delete(task)
    await db.commit()
