import asyncpg
import asyncio

async def test():
    # Connect to gatewayguard database
    conn_str = "postgresql://postgres:postgres@localhost:5432/gatewayguard"
    print(f"🔌 Trying: {conn_str}")
    
    try:
        conn = await asyncpg.connect(conn_str)
        print("✅ CONNECTION SUCCESSFUL!")
        
        # Check if our tables exist
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public';")
        print(f"📊 Tables found: {[t['tablename'] for t in tables]}")
        
        await conn.close()
        print("\n✅ Working connection string found!")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("\n💡 Trying alternative method...")
        
        # Try with container IP
        conn_str2 = "postgresql://postgres:postgres@172.18.0.3:5432/gatewayguard"
        print(f"🔌 Trying: {conn_str2}")
        
        try:
            conn = await asyncpg.connect(conn_str2)
       CONNECTION SUCCESSFUL!")
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public';")
            print(f"📊 Tables found: {[t['tablename'] for t in tables]}")
            await conn.close()
        except Exception as e2:
            print(f"❌ Failed: {e2}")

asyncio.run(test())
