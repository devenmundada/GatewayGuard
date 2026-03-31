import asyncpg
import asyncio

async def test():
    # Try connecting with a timeout
    try:
        conn = await asyncpg.connect(
            user='postgres',
            password='postgres',
            database='postgres',  # Connect to default database first
            host='localhost',
            port=5432,
            timeout=5
        )
        print("✅ Connected to postgres database!")
        
        # Now check if gatewayguard exists
        result = await conn.fetch("SELECT datname FROM pg_database WHERE datname='gatewayguard'")
        if result:
            print(f"✅ gatewayguard database exists!")
            
            # Switch to gatewayguard
            await conn.close()
            conn = await asyncpg.connect(
                user='postgres',
                password='postgres',
                database='gatewayguard',
                host='localhost',
                port=5432,
                timeout=5
            )
            
        # List tables
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            print(f"📊 Tables in gatewayguard: {[t['tablename'] for t in tables]}")
        else:
            print("❌ gatewayguard database does not exist")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
