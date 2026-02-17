import asyncio
from core.integrated_search import IntegratedHotelSearch
import os

async def main():
    # Test the integrated search
    search = IntegratedHotelSearch(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        use_vector_ranking=False  # Disable vector ranking for faster test
    )
    
    await search.connect()
    
    # Test searching for Dhaka
    print("Testing search for 'hotels in dhaka'...")
    results = await search.search(query="hotels in dhaka", limit=5)
    
    print(f"\n✅ Found {len(results)} hotels in Dhaka:")
    for hotel in results:
        print(f"  - {hotel.hotel_name} (${hotel.base_price_per_night}/night)")
    
if __name__ == "__main__":
    asyncio.run(main())
