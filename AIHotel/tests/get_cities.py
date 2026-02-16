import asyncio
from core.database import HotelDatabase

async def main():
    db = HotelDatabase()
    await db.connect()
    cities = await db.get_cities()
    print("Available Cities:", cities)
    
if __name__ == "__main__":
    asyncio.run(main())
