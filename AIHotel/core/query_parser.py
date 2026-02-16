"""
Natural Language Query Parser for Hotel Search.

Extracts structured filters from natural language queries:
- City/Location
- Price range
- Amenities
- Room type
- Number of rooms
- Ratings
"""
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchFilters:
    """Structured search filters extracted from natural language."""
    city: Optional[str] = None
    country: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    amenities: List[str] = None
    room_type: Optional[str] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None  # For filtering "less than X rating"
    number_of_rooms_min: Optional[int] = None
    semantic_query: str = ""  # The vibe/description part
    
    def __post_init__(self):
        if self.amenities is None:
            self.amenities = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ChromaDB filtering."""
        filters = {}
        
        if self.city:
            filters["city"] = self.city.lower()
        if self.country:
            filters["country"] = self.country.lower()
        if self.room_type:
            filters["room_type"] = self.room_type.lower()
        
        return filters
    
    def to_sql_where(self) -> Dict[str, Any]:
        """Convert to SQL-like where clause."""
        where = {}
        
        if self.city:
            where["city__iexact"] = self.city
        if self.country:
            where["country__iexact"] = self.country
        if self.price_min is not None:
            where["price__gte"] = self.price_min
        if self.price_max is not None:
            where["price__lte"] = self.price_max
        if self.min_rating is not None:
            where["average_rating__gte"] = self.min_rating
        if self.room_type:
            where["room_type__iexact"] = self.room_type
        if self.number_of_rooms_min is not None:
            where["number_of_rooms__gte"] = self.number_of_rooms_min
        
        return where


class QueryParser:
    """
    Parse natural language queries into structured filters + semantic search.
    
    Example queries:
    - "Show me hotels in Dhaka under $50"
    - "Luxury hotels in New York with pool and spa"
    - "Budget friendly hotels near beach in Miami"
    - "5-star hotels with free WiFi in Boston"
    """
    
    # City patterns (case-insensitive with "from" support)
    CITY_PATTERNS = [
        r"(?:in|at|near|from)\s+([a-zA-Z][a-zA-Z\s]+?)(?:\s+(?:with|under|below|hotel|city|area|\?|!)|,|$)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:hotels|hotel)",
    ]
    
    # Price patterns
    PRICE_PATTERNS = [
        r"under\s+\$?(\d+(?:\.\d+)?)",
        r"below\s+\$?(\d+(?:\.\d+)?)",
        r"less\s+than\s+\$?(\d+(?:\.\d+)?)",
        r"max\s+\$?(\d+(?:\.\d+)?)",
        r"budget\s+\$?(\d+(?:\.\d+)?)",
        r"\$(\d+(?:\.\d+)?)\s+or\s+less",
        r"between\s+\$?(\d+(?:\.\d+)?)\s+(?:and|to|-)\s+\$?(\d+(?:\.\d+)?)",
        r"\$(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)",
    ]
    
    # Amenity keywords
    AMENITIES = {
        "pool": ["pool", "swimming pool", "pool access"],
        "wifi": ["wifi", "wi-fi", "internet", "free wifi"],
        "gym": ["gym", "fitness", "fitness center", "workout"],
        "spa": ["spa", "massage", "wellness"],
        "parking": ["parking", "valet", "garage"],
        "restaurant": ["restaurant", "dining", "food"],
        "bar": ["bar", "lounge", "pub"],
        "beach": ["beach", "beach access", "beachfront", "oceanfront"],
        "breakfast": ["breakfast", "morning meal"],
        "pet": ["pet", "dog friendly", "cat friendly", "pet friendly"],
        "airport": ["airport shuttle", "airport transfer"],
        "conference": ["conference", "meeting room", "business center"],
        "kitchen": ["kitchen", "kitchenette", "cooking"],
    }
    
    # Room type keywords
    ROOM_TYPES = {
        "suite": ["suite", "luxury suite"],
        "deluxe": ["deluxe", "deluxe room"],
        "standard": ["standard", "standard room"],
        "presidential": ["presidential", "presidential suite"],
    }
    
    # Rating keywords
    RATING_PATTERNS = [
        r"(\d)[\s-]?star",
        r"rating\s+(?:above|over|at\s+least)\s+(\d(?:\.\d)?)",
        r"rated\s+(\d(?:\.\d)?)\s+or\s+(?:higher|above)",
        r"(\d(?:\.\d)?)\+",  # 4.5+ pattern
        r"(\d(?:\.\d)?)\s+(?:and\s+)?(?:more|above)",  # 4.5 and more, 4.5 above
        r"(?:above|over)\s+(\d(?:\.\d)?)",  # above 4.5
    ]
    
    def parse(self, query: str) -> SearchFilters:
        """
        Parse natural language query into structured filters.
        
        Args:
            query: Natural language search query
            
        Returns:
            SearchFilters object with extracted filters
        """
        filters = SearchFilters()
        query_lower = query.lower()
        
        # Extract city
        filters.city = self._extract_city(query)
        
        # Extract price range
        price_min, price_max = self._extract_price_range(query_lower)
        filters.price_min = price_min
        filters.price_max = price_max
        
        # Extract amenities
        filters.amenities = self._extract_amenities(query_lower)
        
        # Extract room type
        filters.room_type = self._extract_room_type(query_lower)
        
        # Extract rating (handles both min and max)
        min_rating, max_rating = self._extract_rating(query_lower)
        filters.min_rating = min_rating
        filters.max_rating = max_rating
        
        # Build semantic query (remove extracted filters)
        filters.semantic_query = self._build_semantic_query(
            query, filters
        )
        
        logger.info(f"Parsed query: {query}")
        logger.info(f"Filters: city={filters.city}, price_max={filters.price_max}, "
                   f"amenities={filters.amenities}, min_rating={filters.min_rating}, "
                   f"max_rating={filters.max_rating}")
        logger.info(f"Semantic query: {filters.semantic_query}")
        
        return filters
    
    def _extract_city(self, query: str) -> Optional[str]:
        """Extract city from query (case-insensitive, validates against known cities)."""
        # Common cities (extend as needed)
        known_cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
            "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
            "Miami", "Boston", "Seattle", "Denver", "Portland", "Nashville",
            "San Francisco", "Minneapolis", "Aspen", "Napa Valley",
            "New Orleans", "Dhaka", "Mumbai", "Delhi", "Bangalore",
            "Miami Beach", "Las Vegas", "Orlando", "Atlanta", "Austin",
            "Charlotte", "Detroit", "Las Colinas", "Honolulu"
        ]
        
        query_lower = query.lower()
        
        # First, try direct match with known cities using location keywords
        for city in known_cities:
            city_lower = city.lower()
            # Match patterns: "in Miami", "from Dhaka", "near Boston", etc.
            if re.search(rf"\b(?:in|at|near|from)\s+{re.escape(city_lower)}\b", query_lower):
                return city
        
        # Fallback: try pattern matching but VALIDATE against known cities
        for pattern in self.CITY_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                city = match.group(1).strip().title()
                
                # Only accept if it matches a known city
                for known in known_cities:
                    if known.lower() == city.lower():
                        return known
        
        return None
    
    def _extract_price_range(self, query: str) -> tuple[Optional[float], Optional[float]]:
        """Extract price range from query."""
        price_min = None
        price_max = None
        
        # Check for range patterns first (but not rating ranges)
        range_match = re.search(
            r"between\s+\$(\d+(?:\.\d+)?)\s+(?:and|to|-)\s+\$?(\d+(?:\.\d+)?)",
            query
        )
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            return price_min, price_max
        
        range_match = re.search(r"\$(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)", query)
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            return price_min, price_max
        
        # Check for max patterns - but ONLY if dollar sign is present or number > 10
        # This avoids confusing "rating less than 4.5" with price
        under_match = re.search(r"(?:under|below|less\s+than|max)\s+\$(\d+(?:\.\d+)?)", query)
        if under_match:
            price_max = float(under_match.group(1))
            return price_min, price_max
        
        # Only treat as price if no dollar sign AND value is > 10 (likely price not rating)
        under_match = re.search(r"(?:under|below|max\s+price)\s+(\d{2,}(?:\.\d+)?)", query)
        if under_match:
            price_max = float(under_match.group(1))
            return price_min, price_max
        
        # Keywords for budget/cheap
        if any(word in query for word in ["budget", "cheap", "affordable", "economical"]):
            if price_max is None:
                price_max = 100.0
        
        # Keywords for luxury/expensive
        if any(word in query for word in ["luxury", "expensive", "premium", "5-star", "five star"]):
            if price_min is None:
                price_min = 200.0
        
        return price_min, price_max
    
    def _extract_amenities(self, query: str) -> List[str]:
        """Extract amenities from query."""
        found_amenities = []
        
        for amenity, keywords in self.AMENITIES.items():
            for keyword in keywords:
                if keyword in query:
                    found_amenities.append(amenity.title())
                    break
        
        return found_amenities
    
    def _extract_room_type(self, query: str) -> Optional[str]:
        """Extract room type from query."""
        for room_type, keywords in self.ROOM_TYPES.items():
            for keyword in keywords:
                if keyword in query:
                    return room_type
        
        return None
    
    def _extract_rating(self, query: str) -> tuple[Optional[float], Optional[float]]:
        """Extract minimum and maximum rating from query."""
        min_rating = None
        max_rating = None
        
        # Check for "less than" or "below" rating patterns
        # This handles "rating less than 4.5" or "below 4.5"
        less_than_match = re.search(
            r"rating\s+(?:less\s+than|below|under)\s+(\d(?:\.\d)?)",
            query
        )
        if less_than_match:
            max_rating = float(less_than_match.group(1))
            return min_rating, max_rating
        
        # Check for rating between X and Y
        between_match = re.search(
            r"(?:rating|rated)?\s*between\s+(\d(?:\.\d)?)\s+(?:and|to)\s+(\d(?:\.\d)?)",
            query
        )
        if between_match:
            min_rating = float(between_match.group(1))
            max_rating = float(between_match.group(2))
            return min_rating, max_rating
        
        # Check for "X and more" / "X+" / "above X" patterns (minimum rating)
        more_than_match = re.search(
            r"(\d(?:\.\d)?)\s+(?:and\s+)?(?:more|above|or\s+higher|or\s+more)\s+rating",
            query
        )
        if more_than_match:
            min_rating = float(more_than_match.group(1))
            return min_rating, max_rating
        
        # Standard patterns for minimum rating
        for pattern in self.RATING_PATTERNS:
            match = re.search(pattern, query)
            if match:
                rating = float(match.group(1))
                if rating <= 5:  # Valid rating
                    min_rating = rating
                    break
        
        return min_rating, max_rating
    
    def _build_semantic_query(
        self, 
        original_query: str,
        filters: SearchFilters
    ) -> str:
        """
        Build semantic search query by removing hard filters.
        Keep descriptive words like 'luxury', 'cozy', 'modern', etc.
        """
        query = original_query.lower()
        
        # Remove city mentions
        if filters.city:
            query = re.sub(
                r"(?:in|at|near)\s+" + re.escape(filters.city.lower()),
                "",
                query,
                flags=re.IGNORECASE
            )
        
        # Remove price mentions
        query = re.sub(r"under\s+\$?\d+(?:\.\d+)?", "", query)
        query = re.sub(r"below\s+\$?\d+(?:\.\d+)?", "", query)
        query = re.sub(r"\$\d+(?:\.\d+)?(?:\s*-\s*\$?\d+(?:\.\d+)?)?", "", query)
        
        # Remove rating mentions
        query = re.sub(r"\d[\s-]?star", "", query)
        
        # Remove "hotel/hotels" 
        query = re.sub(r"\bhotels?\b", "", query)
        
        # Clean up whitespace
        query = " ".join(query.split())
        
        # If query is empty or too short, use original
        if len(query.strip()) < 3:
            return original_query
        
        return query.strip()
