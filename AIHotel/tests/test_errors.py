
import asyncio
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch

# Set up logging to only show relevant info
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_error_handling():
    print("\n🚀 Testing Model's Error Handling...")
    
    # Initialize components
    search_system = IntegratedHotelSearch()
    
    # Force use of SQLite for testing
    if os.path.exists("hotel.db"):
        import core.sqlite_db
        search_system.db = core.sqlite_db.SQLiteHotelDatabase()
    
    await search_system.connect()
    orchestrator = TravelOrchestrator(search_system)
    
    test_queries = [
        "Find me a hotel in Atlantis", # Invalid City
        "Show hotels under $-100 dollars", # Negative price
        "Find hotels with rating of 12 stars", # Rating > 10
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: '{query}' ---")
        response = await orchestrator.run(query)
        print(f"Response: {response.get('natural_language_response')}")
    
    await search_system.close()

if __name__ == "__main__":
    asyncio.run(test_error_handling())
