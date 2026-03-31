import asyncio
import asyncpg

async def test():
    try:
        # Try with timeout
        conn = await asyncio.wait_for(
            asyncpg.connect(
                'postgresql://postgres:postgres@172.18.0.3:5432/gatewayguard',
                timeout=5
            ),
            timeout=5
        )
        print("✅ Connected successfully!")
        
        # Test query
        result = await conn.fetch("SELECT 1 as test")
        print(f"Query result: {result}")
        
        await conn.close()
        return True
        
    except asyncio.TimeoutError:
        print("❌ Connection timeout - can't reach PostgreSQL")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

asyncio.run(test())
