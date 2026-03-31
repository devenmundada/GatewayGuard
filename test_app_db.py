import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def test():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            tables = result.fetchall()
            print(f"✅ Connected to database!")
            print(f"📊 Tables: {[t[0] for t in tables]}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await engine.dispose()

asyncio.run(test())
