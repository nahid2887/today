"""Discover database schema - find actual table names."""
import asyncio
import asyncpg


async def discover_schema():
    """Discover actual database schema."""
    print("🔍 Discovering Database Schema...")
    
    try:
        conn = await asyncpg.connect(
            host="10.10.13.27",
            port=5433,
            database="hotel_db",
            user="hotel_user",
            password="hotel_pass"
        )
        
        print("✅ Connected!\n")
        
        # List all tables
        print("📋 Tables in database:")
        tables = await conn.fetch("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
        """)
        
        for t in tables:
            print(f"  • {t['table_schema']}.{t['table_name']}")
        
        # For each table, show columns
        for t in tables:
            table_name = f"{t['table_schema']}.{t['table_name']}"
            print(f"\n📊 Schema for {table_name}:")
            
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """, t['table_schema'], t['table_name'])
            
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  • {col['column_name']} ({col['data_type']}) {nullable}")
            
            # Sample row count
            try:
                count = await conn.fetchval(f'SELECT COUNT(*) FROM {table_name}')
                print(f"  → Rows: {count}")
            except:
                pass
        
        await conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(discover_schema())
