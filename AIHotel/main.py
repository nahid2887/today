"""
Hotel Recommendation Agent - Main Entry Point

This module provides the primary interface for the hotel recommendation system.
Uses direct database access for real-time hotel data.
"""
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional

# Patterns that mean "give me the next batch of hotels" rather than a new search.
# Checked against session_pending_hotels before calling the agent.
# NOTE: filler words like "some", "me", "us", "can you" are ignored via lookahead logic.
_SHOW_MORE_RE = re.compile(
    r'(?:'
    # "show ... more" with optional filler ("show some more", "can you show me more")
    r'show\s+(?:\w+\s+){0,3}more'
    r'|more\s+hotels?|more\s+options?|more\s+results?|see\s+more'
    r'|any\s+(?:more|others?)\b|other\s+hotels?|what\s+else|more\s+please'
    r'|next\s+(?:hotels?|ones?)|rest\s+of|remaining\s+hotels?'
    r'|suggest\s+more|give\s+more|list\s+more|any\s+more'
    r'|show\s+(?:me\s+)?(?:some\s+)?more'
    r')|^(?:more|others?|next|continue|remaining)$',
    re.IGNORECASE
)

_CHEAPER_RE = re.compile(r'cheap|budget|affordable|inexpensive|low.?cost|less\s+expensive', re.IGNORECASE)
_LUXURY_RE  = re.compile(r'luxury|premium|upscale|expensive|5.?star|five.?star', re.IGNORECASE)

def _is_show_more_query(text: str) -> bool:
    """Return True if the query is asking for more results from the current batch."""
    return bool(_SHOW_MORE_RE.search(text.strip()))

from core.integrated_search import IntegratedHotelSearch
from agents.orchestrator import TravelOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances (initialized once)
_search_system: Optional[IntegratedHotelSearch] = None
_orchestrator: Optional[TravelOrchestrator] = None


async def sync_hotel_data() -> Dict[str, Any]:
    """
    OBSOLETE: The system now uses direct database queries.
    This remains for backward compatibility with existing tests and scripts.
    """
    logger.info("Sync requested (OBSOLETE: system uses live database queries)")
    count = await get_hotel_count()
    return {
        "status": "success",
        "count": count,
        "message": "System is using direct database connection (sync not required)"
    }


async def initialize_system():
    """
    Initialize the search system and orchestrator.
    
    This should be called once during application startup.
    Uses direct database access for real-time queries.
    """
    global _search_system, _orchestrator
    
    if _search_system is None:
        logger.info("Initializing IntegratedHotelSearch...")
        _search_system = IntegratedHotelSearch(use_vector_ranking=True)
        await _search_system.connect()
        logger.info("✅ Connected to database")
    
    if _orchestrator is None:
        logger.info("Initializing TravelOrchestrator...")
        _orchestrator = TravelOrchestrator(_search_system)
    
    logger.info("System initialized successfully")


async def get_database_statistics() -> Dict[str, Any]:
    """
    Get real-time database statistics.
    
    Returns:
        Dictionary with total hotels, cities, price range, etc.
    """
    global _search_system
    
    if _search_system is None:
        await initialize_system()
    
    return await _search_system.get_statistics()


async def run_travel_chat(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    shown_hotel_ids: Optional[List[int]] = None,
    last_hotels: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main entry point for the travel assistant.
    
    Uses direct database access for real-time hotel recommendations.
    
    Args:
        query: User's natural language query
        history: Optional conversation history in format [{"role": "user", "content": "..."}, ...]
        shown_hotel_ids: Optional list of hotel IDs already shown in this session
        last_hotels: Optional list of hotels from the previous turn
    
    Returns:
        Dictionary containing:
        {
            "natural_language_response": "Response text...",
            "recommended_hotels": [...],
            "shown_hotel_ids": [...],
            "last_hotels": [...],
            "metadata": {...}
        }
    """
    global _orchestrator, _search_system
    
    # Initialize system if not already done
    if _orchestrator is None or _search_system is None:
        await initialize_system()
    
    logger.info(f"Processing query: {query}")
    
    try:
        # Run the orchestrator workflow
        result = await _orchestrator.run(
            query, 
            history or [], 
            shown_hotel_ids or [],
            last_hotels=last_hotels
        )
        
        query_type = result.get('metadata', {}).get('query_type', 'unknown')
        hotel_count = len(result.get('recommended_hotels', []))
        
        logger.info(f"Query type: {query_type}, Hotels: {hotel_count}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in run_travel_chat: {e}", exc_info=True)
        return {
            "natural_language_response": "I apologize, but I encountered an error processing your request. Please try again.",
            "recommended_hotels": [],
            "shown_hotel_ids": shown_hotel_ids or [],
            "metadata": {
                "query": query,
                "error": str(e)
            }
        }


async def get_hotel_count() -> int:
    """
    Get the total number of hotels in the database.
    
    Returns:
        Number of hotels indexed
    """
    try:
        stats = await get_database_statistics()
        return stats.get('total_hotels', 0)
    except Exception as e:
        logger.error(f"Error getting hotel count: {e}")
        return 0


# CLI for testing
async def main():
    """Command-line interface for testing the orchestrator."""
    print("=" * 60)
    print("Travel Assistant - Interactive Test Mode")
    print("=" * 60)
    print("\nI can help with:")
    print("  🗣️  Normal chat (greetings, casual talk)")
    print("  🌍 Travel information (destinations, tips)")
    print("  🏨 Hotel search (recommendations, filters)")
    print("=" * 60)
    
    # Initialize system
    await initialize_system()
    
    # Check if data is synced
    count = await get_hotel_count()
    print(f"\nHotels in database: {count}")
    
    if count == 0:
        print("\nNo hotels found in database. Please ensure PostgreSQL is populated.")
    
    print("\n" + "=" * 60)
    print("Ready! (Type 'quit' to exit, 'sync' for status, 'reset' to clear session)")
    print("=" * 60)
    
    # Interactive loop with session state
    history = []
    shown_hotel_ids = []
    last_hotels: List[Dict[str, Any]] = []         # full result pool from previous turn
    session_pending_hotels: List[Dict[str, Any]] = []  # fetched but not yet shown
    
    while True:
        try:
            print("\n")
            query = input("Your query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if query.lower() == 'sync':
                print("\nReporting current status...")
                sync_result = await sync_hotel_data()
                print(f"Result: {sync_result}")
                continue
            
            if query.lower() == 'reset':
                print("\n✓ Session reset! Clearing history and shown hotels.")
                history = []
                shown_hotel_ids = []
                last_hotels = []
                session_pending_hotels = []
                continue
            
            print("\nProcessing...")

            # ── Show-more shortcut: serve the next batch without calling the agent ──
            if session_pending_hotels and _is_show_more_query(query):
                # Apply optional price refinement on the pending batch
                pending_pool = list(session_pending_hotels)
                if _CHEAPER_RE.search(query):
                    pending_pool.sort(key=lambda h: h.get('base_price_per_night') or 999999)
                elif _LUXURY_RE.search(query):
                    pending_pool.sort(key=lambda h: -(h.get('base_price_per_night') or 0))
                batch = pending_pool[:3]
                session_pending_hotels = pending_pool[3:]
                new_ids = [h['id'] for h in batch if h.get('id')]
                shown_hotel_ids = list(set(shown_hotel_ids + new_ids))
                city = batch[0].get('city', '') if batch else ''
                names = ', '.join(h.get('hotel_name', 'Hotel') for h in batch)
                more_note = (
                    f" I have {len(session_pending_hotels)} more available — just ask!"
                    if session_pending_hotels else
                    " That's all the options I found."
                )
                is_external = any(h.get('source') == 'external' for h in batch)
                disclaimer = (
                    "\n\n⚠️ *These are external results not in our partner network. "
                    "Book directly via the links provided. We cannot guarantee availability or pricing.*"
                    if is_external else ""
                )
                plural = 's' if len(batch) != 1 else ''
                resp_text = (
                    f"Here are {len(batch)} more hotel{plural}"
                    + (f" in {city}" if city else "")
                    + f": {names}.{more_note}{disclaimer}"
                )
                result = {
                    "natural_language_response": resp_text,
                    "recommended_hotels": batch,
                    "pending_hotels": session_pending_hotels,
                    "shown_hotel_ids": shown_hotel_ids,
                    "last_hotels": last_hotels,
                    "metadata": {
                        "query_type": "hotel_search",
                        "query": query,
                        "total_shown_in_session": len(shown_hotel_ids),
                    },
                }
            else:
                # ── Normal agent call ───────────────────────────────────────────
                # Start fresh pending list; a new search replaces the old one.
                session_pending_hotels = []
                result = await run_travel_chat(query, history, shown_hotel_ids, last_hotels)
                # Store pending hotels and last_hotels for follow-up turns
                session_pending_hotels = result.get('pending_hotels', [])
                last_hotels = result.get('last_hotels', last_hotels)
                shown_hotel_ids = result.get('shown_hotel_ids', shown_hotel_ids)
            
            # Display response
            print("\n" + "=" * 60)
            print("RESPONSE:")
            print("=" * 60)
            print(result['natural_language_response'])
            
            # Display metadata
            metadata = result.get('metadata', {})
            if metadata.get('filters_applied'):
                filters = metadata['filters_applied']
                filter_parts = []
                if filters.get('city'):
                    filter_parts.append(f"City: {filters['city']}")
                if filters.get('min_rating') and filters.get('max_rating'):
                    filter_parts.append(f"Rating: {filters['min_rating']}-{filters['max_rating']}")
                elif filters.get('min_rating'):
                    filter_parts.append(f"Min Rating: {filters['min_rating']}")
                if filters.get('max_price'):
                    filter_parts.append(f"Max Price: ${filters['max_price']}")
                if filter_parts:
                    print(f"\n📊 Filters Applied: {', '.join(filter_parts)}")
            
            if metadata.get('total_shown_in_session', 0) > 0:
                print(f"💡 Session: Hotels shown this session: {metadata['total_shown_in_session']}")
            if session_pending_hotels:
                print(f"➕ {len(session_pending_hotels)} more hotel(s) available — ask 'show more' to see them.")
            
            # Display hotel details
            if result['recommended_hotels']:
                # NEW: Display JSON Data for Frontend UI logic debugging
                import json
                print("\n" + "=" * 60)
                print("FRONTEND RENDER DATA (JSON):")
                print("=" * 60)
                print(json.dumps(result['recommended_hotels'], indent=2))

                print("\n" + "=" * 60)
                print("RECOMMENDED HOTELS:")
                print("=" * 60)
                
                for i, hotel in enumerate(result['recommended_hotels'], 1):
                    name = hotel.get('hotel_name', hotel.get('name', 'N/A'))
                    city = hotel.get('city', 'N/A').title()
                    rating = hotel.get('average_rating', hotel.get('rating')) or 0
                    reviews = hotel.get('total_ratings', hotel.get('reviews_count', 0))
                    price = hotel.get('base_price_per_night', hotel.get('price', 'N/A'))
                    
                    print(f"\n{i}. {name}")
                    print(f"   City: {city}")
                    print(f"   Rating: {rating:.2f}/10 ({reviews} reviews)")
                    print(f"   Price: ${price}")
                    
                    if hotel.get('special_offers'):
                        offers = hotel['special_offers']
                        if isinstance(offers, list):
                            offer_texts = []
                            for offer in offers:
                                if isinstance(offer, dict):
                                    offer_texts.append(offer.get('title', 'Special Offer'))
                                else:
                                    offer_texts.append(str(offer))
                            print(f"   Special Offers: {', '.join(offer_texts)}")
                    
                    if hotel.get('composite_score'):
                        print(f"   Match Score: {hotel['composite_score']:.3f}")
            
            # Update history
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": result['natural_language_response']})
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            logger.error(f"CLI error: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
