import asyncio
import asyncpg

async def test():
    try:
        # Connect to Docker's PostgreSQL
        conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/gatewayguard')
        
        # Check tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        print(f"✅ Connected to Docker PostgreSQL!")
        print(f"📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
