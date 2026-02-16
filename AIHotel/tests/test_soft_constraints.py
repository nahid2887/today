
import asyncio
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch
from core.sqlite_db import SQLiteHotelDatabase

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_soft_constraints():
    print("\n🚀 Testing Smart Filter Expansion (Soft Constraints)...")
    
    # Initialize components
    search_system = IntegratedHotelSearch()
    
    # Force use of SQLite for testing
    if os.path.exists("hotel.db"):
        import core.sqlite_db
        search_system.db = core.sqlite_db.SQLiteHotelDatabase()
    
    await search_system.connect()
    
    orchestrator = TravelOrchestrator(search_system)
    
    # Test queries
    test_queries = [
        "Find a hotel in Sydney with rating 9.0 or higher", # Currently max is 8.9, should relax to 8.5
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: '{query}' ---")
        result = await orchestrator.run(query)
        print(f"Response: {result['natural_language_response']}")
        
        if result['recommended_hotels']:
            print(f"Found {len(result['recommended_hotels'])} hotels after relaxation")
            for h in result['recommended_hotels']:
                print(f" - {h.get('hotel_name')} (Rating: {h.get('average_rating')})")
        else:
            print("❌ Still no hotels found after relaxation")

    await search_system.close()

if __name__ == "__main__":
    asyncio.run(test_soft_constraints())
