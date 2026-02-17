import asyncio
from core.database import HotelDatabase

async def main():
    db = HotelDatabase()
    await db.connect()
    
    async with db.get_connection() as conn:
        # Check all fields for "Dhaka"
        query = """
            SELECT id, hotel_name, city, country, location
            FROM hotel_hotel 
            WHERE LOWER(hotel_name) LIKE '%dhaka%'
               OR LOWER(city) LIKE '%dhaka%'
               OR LOWER(country) LIKE '%dhaka%'
               OR LOWER(location) LIKE '%dhaka%'
        """
        
        results = await conn.fetch(query)
        print(f"Hotels matching 'dhaka' ({len(results)}):")
        for hotel in results:
            print(f"  ID: {hotel['id']}")
            print(f"  Name: {hotel['hotel_name']}")
            print(f"  City: {hotel['city']}")
            print(f"  Country: {hotel['country']}")
            print(f"  Location: {hotel['location']}")
            print()
        
        # Also check Bangladesh hotels
        query2 = """
            SELECT id, hotel_name, city, country, location
            FROM hotel_hotel 
            WHERE LOWER(country) = 'bangladesh'
        """
        
        bd_results = await conn.fetch(query2)
        print(f"\nAll Bangladesh hotels ({len(bd_results)}):")
        for hotel in bd_results:
            print(f"  ID: {hotel['id']}, Name: {hotel['hotel_name']}, City: {hotel['city']}, Location: {hotel['location']}")
    
if __name__ == "__main__":
    asyncio.run(main())
