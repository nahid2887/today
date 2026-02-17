import asyncio
from core.database import HotelDatabase

async def main():
    db = HotelDatabase()
    await db.connect()
    
    # Check for hotels with "Dhaka" in city name
    query = """
        SELECT DISTINCT city 
        FROM hotel_hotel 
        WHERE LOWER(city) LIKE '%dhaka%'
    """
    
    async with db.get_connection() as conn:
        dhaka_cities = await conn.fetch(query)
        print(f"Cities matching 'dhaka': {dhaka_cities}")
        
        # Also get all distinct cities
        all_cities_query = "SELECT DISTINCT city FROM hotel_hotel ORDER BY city"
        all_cities = await conn.fetch(all_cities_query)
        print(f"\nAll cities ({len(all_cities)}):")
        for city in all_cities:
            print(f"  - {city['city']}")
    
if __name__ == "__main__":
    asyncio.run(main())
