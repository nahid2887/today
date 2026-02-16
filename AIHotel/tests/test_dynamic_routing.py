
import asyncio
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch
from core.sqlite_db import SQLiteHotelDatabase
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_routing():
    print("\n🚀 Testing Dynamic Routing and City Awareness...")
    
    # Initialize components
    search_system = IntegratedHotelSearch()
    
    # Force use of SQLite for testing if hotel.db exists
    if os.path.exists("hotel.db"):
        print("📁 Using local hotel.db for testing")
        # We need to monkeypatch or ensure HotelDatabase uses SQLite
        from core.database import HotelDatabase
        import core.sqlite_db
        # Since HotelDatabase is already imported in many places, 
        # let's just make sure IntegratedHotelSearch uses the SQLite one
        search_system.db = core.sqlite_db.SQLiteHotelDatabase()
    
    await search_system.connect()
    
    # Check available cities
    cities = await search_system.get_available_cities()
    print(f"✅ Available cities in DB: {cities}")
    
    orchestrator = TravelOrchestrator(search_system)
    
    # Test queries
    test_queries = [
        "Find luxury hotels in Sydney with a pool",  # Should trigger semantic matching
        "Hotels in Melbourne under $500",           # Should trigger price match reason
        "Any simple stays in Brisbane?",             # Should trigger city match reason
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: '{query}' ---")
        result = await orchestrator.run(query)
        print(f"Intent Classified: {result['metadata'].get('query_type')}")
        print(f"Response Snippet: {result['natural_language_response'][:100]}...")
        if result['recommended_hotels']:
            print(f"Found {len(result['recommended_hotels'])} hotels")
            for h in result['recommended_hotels'][:2]:
                print(f" - {h.get('hotel_name')} ({h.get('city')})")
        else:
            print("❌ No hotels found in response")

    await search_system.close()

if __name__ == "__main__":
    asyncio.run(test_routing())
