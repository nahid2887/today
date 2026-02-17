import asyncio
from core.database import HotelDatabase

async def main():
    db = HotelDatabase()
    await db.connect()
    
    # Test searching for hotels in Dhaka
    hotels = await db.get_all_hotels(city="Dhaka", limit=10)
    
    print(f"Hotels found in Dhaka: {len(hotels)}")
    for hotel in hotels:
        print(f"\n  ID: {hotel['id']}")
        print(f"  Name: {hotel['hotel_name']}")
        print(f"  City: {hotel['city']}")
        print(f"  Location: {hotel['location']}")
        print(f"  Price: ${hotel['base_price_per_night']}")
        print(f"  Rating: {hotel['average_rating']}/10")
    
if __name__ == "__main__":
    asyncio.run(main())
