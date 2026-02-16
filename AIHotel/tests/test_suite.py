import asyncio
import json
import logging
import os
import sys
from typing import List, Dict, Any

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def run_test_suite():
    print("🧪 RUNNING COMPREHENSIVE CORNER CASE TEST SUITE 🧪")
    print("      (USING PRODUCTION POSTGRES DATABASE)        ")
    print("==================================================\n")

    # Initialize System (uses HotelDatabase by default)
    search_system = IntegratedHotelSearch(use_vector_ranking=True)
    await search_system.connect()
    orchestrator = TravelOrchestrator(search_system)

    test_cases = [
        {
            "name": "Typo Correction",
            "queries": ["Find hotels in Sidny"]
        },
        {
            "name": "Negation Handling",
            "queries": ["Hotels in Sydney no pool"]
        },
        {
            "name": "Soft Constraint Relaxation",
            "queries": ["Hotels in Melbourne under $50"] # Assuming no hotels under 50
        },
        {
            "name": "Invalid Input (Negative Price)",
            "queries": ["Hotels in Sydney with price -$100"]
        },
        {
            "name": "Invalid Input (Extreme Rating)",
            "queries": ["Hotels in Perth with rating 11"]
        },
        {
            "name": "No Results Found",
            "queries": ["Hotels in Atlantis"]
        },
        {
            "name": "Multi-turn Refinement",
            "queries": [
                "Find hotels in Sydney with a pool",
                "Which one is the cheapest?",
                "Actually, show me the best rated one instead"
            ]
        },
        {
            "name": "Non-Hotel Query (Travel Info)",
            "queries": ["What is the best time to visit Sydney?"]
        },
        {
            "name": "Conversational Query",
            "queries": ["Hello! Who are you?"]
        },
        {
            "name": "Complex Amenity Search",
            "queries": ["Hotels in Brisbane with wifi, gym and breakfast"]
        }
    ]

    for case in test_cases:
        print(f"▶️ TEST CASE: {case['name']}")
        print("-" * 30)
        
        history = []
        last_hotels = []
        shown_ids = []
        
        for query in case['queries']:
            print(f"User: {query}")
            result = await orchestrator.run(
                query, 
                history=history,
                last_hotels=last_hotels,
                shown_hotel_ids=shown_ids
            )
            
            response = result.get('natural_language_response')
            hotels = result.get('recommended_hotels', [])
            
            print(f"Bot: {response}")
            if hotels:
                names = [h.get('hotel_name') for h in hotels[:2]]
                print(f"Top Hotels: {names} (Total: {len(result.get('last_hotels', []))})")
            
            # Update state for multi-turn if within the same test case
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": response})
            last_hotels = result.get('last_hotels', [])
            shown_ids = result.get('shown_hotel_ids', [])
            print()
            
        print("Done.\n")

    await search_system.close()

if __name__ == "__main__":
    asyncio.run(run_test_suite())
