"""
JSON-based implementation of the Hotel Database for testing.
Matches the interface of HotelDatabase in core/database.py.
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class JSONHotelDatabase:
    """
    Direct JSON file access for hotel data.
    Used for rapid testing with local JSON files.
    """
    
    def __init__(self, json_path: str = "hotels.json"):
        self.json_path = json_path
        self.hotels = []
        logger.info(f"JSONHotelDatabase initialized with {json_path}")

    async def connect(self):
        """Load JSON data into memory."""
        try:
            with open(self.json_path, 'r') as f:
                self.hotels = json.load(f)
            logger.info(f"✅ Loaded {len(self.hotels)} hotels from {self.json_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load JSON database: {e}")
            self.hotels = []

    async def disconnect(self):
        """No-op for JSON."""
        pass

    async def get_all_hotels(
        self,
        city: Optional[str] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        exclude_city: Optional[str] = None,
        exclude_amenities: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Filter hotels in memory."""
        filtered = self.hotels
        
        # Filter by approved (assume id exists implies valid for test)
        # In real json we might not have is_approved field, so we just take all
        
        if city:
            filtered = [h for h in filtered if h.get('city', '').lower() == city.lower()]

        if exclude_city:
            filtered = [h for h in filtered if h.get('city', '').lower() != exclude_city.lower()]
            
        if min_rating is not None:
            filtered = [h for h in filtered if float(h.get('average_rating') or 0) >= min_rating]
            
        if max_rating is not None:
            filtered = [h for h in filtered if float(h.get('average_rating') or 0) < max_rating]
            
        if min_price is not None:
            # Note: base_price_per_night might not exist in some JSON structures
            filtered = [h for h in filtered if float(h.get('base_price_per_night') or 0) >= min_price]
            
        if max_price is not None:
            filtered = [h for h in filtered if float(h.get('base_price_per_night') or 0) <= max_price]
            
        if amenities:
            for amenity in amenities:
                filtered = [
                    h for h in filtered 
                    if any(amenity.lower() in str(a).lower() for a in h.get('amenities', []))
                ]

        if exclude_amenities:
            for amenity in exclude_amenities:
                filtered = [
                    h for h in filtered 
                    if not any(amenity.lower() in str(a).lower() for a in h.get('amenities', []))
                ]

        # Helper to safely convert to float/int
        def safe_float(val, default=0.0):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def safe_int(val, default=0):
            try:
                return int(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        # Sort by rating and reviews
        filtered.sort(key=lambda x: (safe_float(x.get('average_rating')), safe_int(x.get('total_ratings'))), reverse=True)
        
        # Pagination
        results = filtered[offset : offset + limit]
        
        # Format for consistency
        for h in results:
            if h.get('average_rating'):
                h['average_rating'] = float(h['average_rating'])
            if h.get('base_price_per_night'):
                h['base_price_per_night'] = float(h['base_price_per_night'])
                
        return results

    async def get_hotel_by_id(self, hotel_id: int) -> Optional[Dict[str, Any]]:
        for h in self.hotels:
            if h.get('id') == hotel_id:
                hotel = h.copy()
                if hotel.get('average_rating'):
                    hotel['average_rating'] = float(hotel['average_rating'])
                return hotel
        return None

    async def get_cities(self) -> List[str]:
        cities = set()
        for h in self.hotels:
            if h.get('city'):
                cities.add(h['city'])
        return sorted(list(cities))

    async def get_amenities(self) -> List[str]:
        amenities = set()
        for h in self.hotels:
            for a in h.get('amenities', []):
                amenities.add(a)
        return sorted(list(amenities))

    async def get_price_bounds(self) -> Dict[str, float]:
        def safe_float(val, default=0.0):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        prices = [safe_float(h.get('base_price_per_night')) for h in self.hotels if h.get('base_price_per_night')]
        if not prices:
            return {'min': 0.0, 'max': 0.0}
        return {'min': min(prices), 'max': max(prices)}

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "total_hotels": len(self.hotels),
            "total_cities": len(await self.get_cities())
        }
