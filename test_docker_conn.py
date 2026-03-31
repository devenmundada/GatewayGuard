import asyncpg
import asyncio

async def test():
    try:
        conn = await asyncpg.connect(
            user='postgres',
            password='postgres',
            database='gatewayguard',
            host='localhost',
            port=5432,
            timeout=5
        )
        print("✅ Connected to Docker PostgreSQL!")
        
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
        if tables:
            print("\n📊 Tables in gatewayguard:")
            for table in tables:
                print(f"   - {table['tablename']}")
        else:
            print("\n⚠️  No tables found")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

asyncio.run(test())
