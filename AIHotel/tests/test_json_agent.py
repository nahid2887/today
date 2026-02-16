
import asyncio
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch
from core.json_db import JSONHotelDatabase

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_json_database_agent():
    print("\n🚀 Testing Agent with JSON Database (hotels.json)...")
    
    # Initialize JSON Database
    json_db = JSONHotelDatabase("hotels.json")
    
    # Initialize search system and swap its database
    search_system = IntegratedHotelSearch()
    search_system.db = json_db
    
    # Connect
    await search_system.connect()
    
    # Initialize orchestrator
    orchestrator = TravelOrchestrator(search_system)
    
    # Test queries based on JSON data
    test_queries = [
        "Find me hotels in Sydney with a rooftop bar",
        "Show me hotels in Melbourne with a pool",
        "Which one of those Sydney hotels is the best rated?",
    ]
    
    session_history = []
    last_hotels = None
    
    for query in test_queries:
        print(f"\n--- Turn: '{query}' ---")
        
        # We need to manually handle turn state for simple test
        # In real app, the frontend/session manager would pass last_hotels
        result = await orchestrator.run(
            query, 
            history=session_history,
            last_hotels=last_hotels
        )
        
        print(f"Response: {result.get('natural_language_response')}")
        
        # Update state for next turn
        last_hotels = result.get('all_search_results', [])
        session_history.append({"role": "user", "content": query})
        session_history.append({"role": "assistant", "content": result.get('natural_language_response')})
        
        # Print hotel names found
        hotels_names = [h.get('hotel_name') for h in result.get('recommended_hotels', [])]
        print(f"Hotels found: {hotels_names}")
    
    await search_system.close()

if __name__ == "__main__":
    asyncio.run(test_json_database_agent())
