"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    # In test environments pytest-asyncio can run each test on a different event loop.
    # Asyncpg connections are bound to an event loop; if we reuse pooled connections across
    # loops we can hit errors like "another operation is in progress" and
    # "Future attached to a different loop".
    #
    # NullPool ensures we do not reuse connections between tests/loops.
    poolclass=NullPool,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()

async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            # CRUD functions handle commit/refresh when they successfully use the DB.
            # Avoid auto-committing here so that "DB unavailable" fallbacks don't leave the
            # session in a pending-rollback state.
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
