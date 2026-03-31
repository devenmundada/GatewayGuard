import asyncpg
import asyncio

async def test():
    try:
        conn = await asyncpg.connect(
            user='postgres',
            password='postgres',
            database='postgres',
            host='localhost',
            port=5432,
            timeout=5
        )
        print("✅ Connected to postgres database!")
        
        databases = await conn.fetch("SELECT datname FROM pg_database ORDER BY datname;")
        print("\n📊 All databases in PostgreSQL:")
        for db in databases:
            print(f"   - {db['datname']}")
        
        gatewayguard_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = 'gatewayguard');"
        )
        
        if gatewayguard_exists:
            print("\n✅ gatewayguard database EXISTS!")
            await conn.close()
            conn2 = await asyncpg.connect(
                user='postgres',
                password='postgres',
                database='gatewa',
                host='localhost',
                port=5432,
                timeout=5
            )
            print("✅ Successfully connected to gatewayguard database!")
            tables = await conn2.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
            if tables:
                print("\n📊 Tables in gatewayguard:")
                for table in tables:
                    print(f"   - {table['tablename']}")
            else:
                print("\n⚠️  No tables found in gatewayguard database")
            await conn2.close()
        else:
            print("\n❌ gatewayguard database does NOT exist!")
            print("\n💡 To create it, run:")
            print("   docker exec -it gatewayguard-postgres-1 psql -U postgres -c \"CREATE DATABASE gatewayguard;\"")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
