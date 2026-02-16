"""Check amenities data format."""
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host="10.10.13.27",
        port=5433,
        database="hotel_db",
        user="hotel_user",
        password="hotel_pass"
    )
    
    # Check a few hotels
    hotels = await conn.fetch("""
        SELECT hotel_name, city, amenities, images
        FROM hotel_hotel
        WHERE is_approved = 'approved'
        LIMIT 5
    """)
    
    for h in hotels:
        print(f"\n{'='*60}")
        print(f"Hotel: {h['hotel_name']} ({h['city']})")
        print(f"Amenities type: {type(h['amenities'])}")
        print(f"Amenities: {h['amenities']}")
        print(f"Images type: {type(h['images'])}")
        print(f"Images: {h['images']}")
    
    await conn.close()

asyncio.run(check())
