import asyncio
import json
import logging
import os
import sys
from typing import List, Dict, Any, Optional

# Add current directory to path
sys.path.append(os.getcwd())

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch

# Set up logging - set to WARNING to keep CLI clean
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Colors for terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

async def run_chat_service():
    # Print cool header
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("  🏨  AI HOTEL CHATBOI  🏨  ")
    print("      (PRODUCTION DB MODE)     ")
    print("============================")
    print(f"{Colors.ENDC}")

    # Initialize search system (uses HotelDatabase by default)
    # We use vector ranking for better semantic results
    search_system = IntegratedHotelSearch(use_vector_ranking=True)
    
    print(f"{Colors.OKCYAN}Connecting to production database...{Colors.ENDC}")
    await search_system.connect()
    
    # Initialize orchestrator
    orchestrator = TravelOrchestrator(search_system)
    
    session_history = []
    last_hotels = []
    shown_hotel_ids = []

    print(f"{Colors.OKGREEN}✅ Chatboi Online! Type 'exit' to quit.{Colors.ENDC}")
    print(f"{Colors.BOLD}Try: 'Hotels in Sydney with a pool' or 'Cheapest room in Melbourne?'{Colors.ENDC}\n")

    while True:
        try:
            user_input = input(f"{Colors.OKGREEN}{Colors.BOLD}You > {Colors.ENDC}")
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print(f"\n{Colors.OKBLUE}Chatboi > Goodbye! Safe travels!{Colors.ENDC}")
                break
                
            if not user_input.strip():
                continue

            # Run the agent
            result = await orchestrator.run(
                user_input, 
                history=session_history,
                last_hotels=last_hotels,
                shown_hotel_ids=shown_hotel_ids
            )
            
            # Response data
            bot_msg = result.get('natural_language_response', "")
            recommended = result.get('recommended_hotels', [])
            last_hotels_result = result.get('last_hotels', [])
            
            # 1. Print Natural Language Response
            print(f"\n{Colors.OKBLUE}{Colors.BOLD}Chatboi > {Colors.ENDC}{bot_msg}")
            
            # 2. Print JSON Response Data (for developers/testing)
            if recommended:
                print(f"\n{Colors.OKCYAN}{Colors.BOLD}[ FRONTEND RENDER DATA ]{Colors.ENDC}")
                # Simplify for cleaner display, but show the new UI-helper fields
                json_data = []
                for h in recommended:
                    rating = h.get('average_rating', 0.0)
                    scale = "/10" if rating > 5.0 else "/5.0"
                    json_data.append({
                        "name": h.get("hotel_name"),
                        "city": h.get("city"),
                        "rating": f"{rating:.1f}{scale}",
                        "badges": h.get("badges", []),
                        "perks": h.get("perks", []),
                        "thumbnail": h.get("images", [None])[0]
                    })
                print(json.dumps(json_data, indent=2))
            
            # Update state for next turn
            session_history.append({"role": "user", "content": user_input})
            session_history.append({"role": "assistant", "content": bot_msg})
            last_hotels = last_hotels_result
            shown_hotel_ids = result.get('shown_hotel_ids', [])
            
            print(f"\n{Colors.WARNING}(Session: {len(shown_hotel_ids)} hotels shown, {len(last_hotels)} in memory){Colors.ENDC}")
            print("-" * 60 + "\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}System Error: {e}{Colors.ENDC}")

    await search_system.close()

if __name__ == "__main__":
    asyncio.run(run_chat_service())
