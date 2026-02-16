"""
Hotel Recommendation Agent - Main Entry Point

This module provides the primary interface for the hotel recommendation system.
Uses direct database access for real-time hotel data.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional

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
                continue
            
            # Process query with session state
            print("\nProcessing...")
            result = await run_travel_chat(query, history, shown_hotel_ids)
            
            # Update shown hotel IDs from result
            shown_hotel_ids = result.get('shown_hotel_ids', shown_hotel_ids)
            
            # Display response
            print("\n" + "=" * 60)
            print("RESPONSE:")
            print("=" * 60)
            print(result['natural_language_response'])
            
            # Show helpful hint if all hotels were shown
            if "already shown you all" in result['natural_language_response'].lower():
                print("\n💡 Tip: Type 'reset' to clear session and see all hotels again")
            
            # Display metadata
            metadata = result.get('metadata', {})
            if metadata.get('filters_applied'):
                filters = metadata['filters_applied']
                filter_parts = []
                if filters.get('city'):
                    filter_parts.append(f"City: {filters['city']}")
                if filters.get('min_rating'):
                    filter_parts.append(f"Min Rating: {filters['min_rating']}")
                if filters.get('max_price'):
                    filter_parts.append(f"Max Price: ${filters['max_price']}")
                if filter_parts:
                    print(f"\n📊 Filters Applied: {', '.join(filter_parts)}")
            
            if metadata.get('total_shown_in_session', 0) > 0:
                print(f"💡 Session: Shown {metadata['total_shown_in_session']} unique hotels so far")
            
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
                    rating = hotel.get('average_rating', hotel.get('rating', 0))
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
    asyncio.run(main())
