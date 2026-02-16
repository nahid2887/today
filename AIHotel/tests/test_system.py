"""
Test the complete integrated system end-to-end.
"""
import asyncio
from main import initialize_system, run_travel_chat, get_database_statistics


async def test_system():
    """Test the complete system."""
    print("🧪 Testing Integrated Hotel Search System\n")
    
    # Initialize
    print("1️⃣ Initializing system...")
    await initialize_system()
    print("✅ System initialized\n")
    
    # Get stats
    print("2️⃣ Getting database statistics...")
    stats = await get_database_statistics()
    print(f"   Total Hotels: {stats['total_hotels']}")
    print(f"   Average Rating: {stats['avg_rating']:.2f}")
    print(f"   Cities: {stats['total_cities']}")
    print(f"   Price Range: ${stats['min_price']:.0f} - ${stats['max_price']:.0f}\n")
    
    # Test queries
    test_queries = [
        "Hello!",
        "hotels in Miami with pool",
        "luxury hotels in San Francisco under $250",
        "4.5+ rated hotels",
    ]
    
    history = []
    shown_ids = []
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i}️⃣ Query: '{query}'")
        print("=" * 60)
        
        result = await run_travel_chat(
            query=query,
            history=history,
            shown_hotel_ids=shown_ids
        )
        
        # Print response
        print(f"\n{result['natural_language_response']}\n")
        
        # Print hotels if any
        hotels = result.get('recommended_hotels', [])
        if hotels:
            print(f"🏨 Found {len(hotels)} hotels:")
            for j, hotel in enumerate(hotels, 1):
                price = hotel.get('base_price_per_night', 0)
                rating = hotel.get('average_rating', 0)
                city = hotel.get('city', 'Unknown')
                name = hotel.get('hotel_name', 'Unknown')
                print(f"   {j}. {name} ({city})")
                print(f"      ${price:.0f}/night | ⭐{rating:.2f}")
        
        # Update state
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": result['natural_language_response']})
        shown_ids = result.get('shown_hotel_ids', [])
        
        print("\n")


if __name__ == "__main__":
    asyncio.run(test_system())
