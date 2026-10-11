import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.db.models import Base


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created:", ", ".join(Base.metadata.tables))


asyncio.run(main())
