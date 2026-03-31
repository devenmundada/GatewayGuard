import asyncpg
import asyncio

async def test():
    # Try different connection strings
    connection_strings = [
        "postgresql://postgres:postgres@localhost:5432/gatewayguard",
        "postgresql://postgres:postgres@127.0.0.1:5432/gatewayguard",
        "postgresql://postgres:postgres@host.docker.internal:5432/gatewayguard",
    ]
    
    for conn_str in connection_strings:
        print(f"\n🔌 Trying: {conn_str}")
        try:
            conn = await asyncpg.connect(conn_str)
            print("✅ CONNECTION SUCCESSFUL!")
            
            # Check if tables exist
            result = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public';")
            print(f"📊 Tables found: {[r['tablename'] for r in result]}")
            
            await conn.close()
            print(f"\n💡 USE THIS CONNECTION: {conn_str}")
            return conn_str
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    print("nection worked")
    return None

asyncio.run(test())
