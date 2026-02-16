
import asyncio
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_multi_turn_memory():
    print("\n🚀 Testing Multi-Turn Memory Management...")
    
    # Initialize components
    search_system = IntegratedHotelSearch()
    
    # Force use of SQLite for testing
    if os.path.exists("hotel.db"):
        import core.sqlite_db
        search_system.db = core.sqlite_db.SQLiteHotelDatabase()
    
    await search_system.connect()
    
    orchestrator = TravelOrchestrator(search_system)
    
    # Turn 1: Initial search
    print("\n--- Turn 1: Initial Search ---")
    query_1 = "Show me hotels in Sydney"
    result_1 = await orchestrator.run(query_1)
    
    print(f"Response: {result_1['natural_language_response']}")
    print(f"Hotels found: {[h.get('hotel_name') for h in result_1['recommended_hotels']]}")
    
    # Turn 2: Follow-up question (Refinement)
    print("\n--- Turn 2: Follow-up (Which is cheapest?) ---")
    query_2 = "Which one is the cheapest?"
    
    # Pass history and last_hotels from turn 1
    history = [
        {"role": "user", "content": query_1},
        {"role": "assistant", "content": result_1['natural_language_response']}
    ]
    
    result_2 = await orchestrator.run(
        query_2, 
        history=history, 
        last_hotels=result_1['last_hotels'],
        shown_hotel_ids=result_1['shown_hotel_ids']
    )
    
    print(f"Response: {result_2['natural_language_response']}")
    if result_2['recommended_hotels']:
        print(f"Top choice: {result_2['recommended_hotels'][0].get('hotel_name')} - Price: {result_2['recommended_hotels'][0].get('price')}")

    await search_system.close()

if __name__ == "__main__":
    asyncio.run(test_multi_turn_memory())
