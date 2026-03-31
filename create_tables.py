import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.db.models import Base
from app.config import settings

async def create_tables():
    print(f"🔌 Connecting to: {settings.DATABASE_URL}")
    
    # First test connection with asyncpg directly
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="postgres"
        )
        # Check if gatewayguard database exists
        result = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'gatewayguard'")
        if not result:
            print("📦 Creating database 'gatewayguard'...")
            await conn.execute("CREATE DATABASE gatewayguard")
            print("✅ Database created!")
        await conn.close()
    except Exception as e:
        print(f"⚠️  Connection check warning: {e}")
    
    # Now contewayguard and create tables
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    try:
        async with engine.begin() as conn:
            # Test connection
            result = await conn.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Tables created successfully!")
            print("\n📊 Tables created:")
            print("   - users")
            print("   - tasks")
            print("   - refresh_tokens")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check if PostgreSQL is running: docker ps | grep postgres")
        print("2. Try: docker compose restart postgres")
        print("3. Check logs: docker compose logs postgres")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_tables())
