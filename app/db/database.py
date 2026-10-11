"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

if settings.ENVIRONMENT.lower() == "testing":
    # pytest-asyncio gives every test its own event loop, and asyncpg connections are
    # bound to the loop that created them, so tests must not reuse pooled connections.
    _engine_options = {"poolclass": NullPool}
else:
    # Real pool: connections are reused across requests instead of paying a TCP + auth
    # handshake to PostgreSQL on every request. 4 gunicorn workers x (5 + 5) = 40
    # connections max, well under PostgreSQL's default of 100.
    _engine_options = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,   # drop dead connections (e.g. after a DB restart)
        "pool_recycle": 1800,
        "pool_timeout": 5,       # fail fast with 503 rather than queue forever
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT.lower() == "development",
    connect_args={"timeout": 5},  # asyncpg connect timeout (seconds)
    **_engine_options,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency that yields a session and rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
