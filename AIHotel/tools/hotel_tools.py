"""
Hotel Tools for Live Data Fetching.

This module provides tools to fetch real-time hotel data including
pricing, special offers, and current availability.
"""
import asyncio
import httpx
import logging
from typing import Dict, Any, List, Optional
from langchain.tools import tool

from config import HOTEL_DETAILS_ENDPOINT, REQUEST_TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_hotel_details(hotel_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch live hotel details from the backend API.
    
    Args:
        hotel_id: The unique hotel identifier
        
    Returns:
        Dictionary containing live hotel data or None if failed
    """
    url = HOTEL_DETAILS_ENDPOINT.format(id=hotel_id)
    
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Successfully fetched details for hotel ID: {hotel_id}")
            return data
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching hotel {hotel_id}: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error fetching hotel {hotel_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching hotel {hotel_id}: {e}")
        return None


@tool
async def get_live_hotel_details(hotel_id: int) -> Dict[str, Any]:
    """
    Fetch real-time hotel details including pricing and special offers.
    
    This tool retrieves the latest information from the backend API to ensure
    the agent provides current pricing, availability, and promotional offers.
    
    Args:
        hotel_id: The unique identifier for the hotel
        
    Returns:
        Dictionary containing:
        - id: Hotel ID
        - name: Hotel name
        - city: City location
        - price: Current price
        - special_offers: List of current promotions
        - amenities: Available amenities
        - rating: Current rating
        - And other live data from the API
    """
    details = await fetch_hotel_details(hotel_id)
    
    if details is None:
        return {
            "error": f"Failed to fetch details for hotel ID {hotel_id}",
            "hotel_id": hotel_id
        }
    
    return details


async def get_live_hotel_details_batch(hotel_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch live details for multiple hotels concurrently.
    
    This is more efficient than calling get_live_hotel_details multiple times
    sequentially. It fetches all hotel details in parallel.
    
    Args:
        hotel_ids: List of hotel IDs to fetch
        
    Returns:
        List of hotel detail dictionaries
    """
    if not hotel_ids:
        return []
    
    logger.info(f"Fetching live details for {len(hotel_ids)} hotels: {hotel_ids}")
    
    # Create tasks for concurrent fetching
    tasks = [fetch_hotel_details(hotel_id) for hotel_id in hotel_ids]
    
    # Execute all requests concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None values and exceptions
    valid_results = []
    for hotel_id, result in zip(hotel_ids, results):
        if isinstance(result, Exception):
            logger.error(f"Exception fetching hotel {hotel_id}: {result}")
            valid_results.append({
                "error": str(result),
                "hotel_id": hotel_id
            })
        elif result is not None:
            valid_results.append(result)
        else:
            valid_results.append({
                "error": "No data returned",
                "hotel_id": hotel_id
            })
    
    logger.info(f"Successfully fetched details for {len(valid_results)} hotels")
    return valid_results


def enrich_hotel_with_live_data(
    base_hotel: Dict[str, Any],
    live_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge base hotel data with live API data.
    
    Args:
        base_hotel: Hotel data from vector store
        live_data: Live data from API (can be None if not available)
        
    Returns:
        Enriched hotel dictionary
    """
    # Start with base hotel data
    enriched = base_hotel.copy()
    
    # If no live data, set defaults
    if live_data is None:
        enriched.update({
            "price": None,
            "currency": None,
            "special_offers": [],
            "current_availability": None,
            "live_data_error": "No live data available"
        })
        return enriched
    
    # Update with live data (live data takes precedence)
    if not live_data.get("error"):
        # Handle nested hotel object from API response
        hotel_data = live_data.get("hotel", live_data)
        
        # Extract price from base_price_per_night field
        price = hotel_data.get("base_price_per_night") or hotel_data.get("price")
        if price:
            try:
                price = float(price)
            except (ValueError, TypeError):
                price = None
        
        # Extract special offers
        special_offers = hotel_data.get("active_special_offers", hotel_data.get("special_offers", []))
        
        enriched.update({
            "price": price,
            "currency": hotel_data.get("currency", "USD"),
            "special_offers": special_offers,
            "current_availability": hotel_data.get("availability", True),
            "discount": hotel_data.get("discount"),
            "amenities": hotel_data.get("amenities", base_hotel.get("amenities", [])),
            "images": hotel_data.get("images", []),
            "contact": hotel_data.get("contact", {}),
            "commission_rate": hotel_data.get("commission_rate"),
            # Keep the average_rating from live data if available
            "average_rating": hotel_data.get("average_rating", base_hotel.get("average_rating")),
            "total_ratings": hotel_data.get("total_ratings", base_hotel.get("total_ratings")),
        })
    else:
        # If there's an error, mark it
        enriched["live_data_error"] = live_data.get("error")
    
    return enriched
