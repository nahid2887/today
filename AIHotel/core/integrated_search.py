"""
Integrated Hotel Search System with Database + NL-to-SQL + Vector Ranking.

This module provides a complete search solution that:
1. Queries PostgreSQL database directly for structured filters
2. Uses NL-to-SQL for complex natural language queries
3. Applies vector similarity ranking for semantic relevance
4. Returns ranked, filtered results with all details
"""

import asyncio
import json
from typing import List, Dict, Optional, Any, Tuple, Union
from dataclasses import dataclass
import logging

from core.database import HotelDatabase
from core.nl_to_sql import NLtoSQLConverter, HybridNLSearch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Hotel search result with relevance score."""
    hotel_id: int
    hotel_name: str
    city: str
    country: str
    description: str
    base_price_per_night: float
    amenities: List[str]
    images: List[str]
    average_rating: float
    total_ratings: int
    number_of_rooms: int
    room_type: str
    relevance_score: float = 1.0
    match_reason: Optional[str] = None
    special_offers: Optional[List[Dict]] = None


class IntegratedHotelSearch:
    """
    Complete hotel search system with database + NL-to-SQL + vector ranking.
    
    Features:
    - Direct database queries for fast filtering
    - NL-to-SQL for complex natural language understanding
    - Vector similarity for semantic relevance ranking
    - Hybrid approach: DB filters first, then vector rank
    - Real-time data (no stale cache)
    """
    
    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        use_vector_ranking: bool = True
    ):
        """
        Initialize integrated search system.
        
        Args:
            groq_api_key: API key for NL-to-SQL (optional, uses env var if not provided)
            use_vector_ranking: Whether to apply vector similarity ranking
        """
        self.db = HotelDatabase()
        self.nl_search = HybridNLSearch(groq_api_key) if groq_api_key else None
        self.use_vector_ranking = use_vector_ranking
        
        # Initialize embedding model for vector ranking
        if use_vector_ranking:
            self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            # Performance: Cache embeddings for frequently queried hotels
            self._embedding_cache = {}  # hotel_id -> embedding vector
        else:
            self.embedding_model = None
            self._embedding_cache = None
            
        self._connected = False
        self._available_cities = []
        self._available_amenities = []
        self._price_bounds = {'min': 0, 'max': 0}
    
    async def connect(self):
        """Connect to database and initialize resources."""
        if not self._connected:
            await self.db.connect()
            self._connected = True
            # Fetch and cache available cities, amenities, and price bounds
            try:
                self._available_cities = await self.db.get_cities()
                self._available_amenities = await self.db.get_amenities()
                self._price_bounds = await self.db.get_price_bounds()
                
                logger.info(f"✅ Integrated search system connected.")
                logger.info(f"   - Cities found: {len(self._available_cities)}")
                logger.info(f"   - Amenities found: {len(self._available_amenities)}")
                logger.info(f"   - Price range: ${self._price_bounds['min']} - ${self._price_bounds['max']}")
            except Exception as e:
                logger.error(f"Failed to fetch discovery metadata during connection: {e}")
                self._available_cities = []
                self._available_amenities = []
                self._price_bounds = {'min': 0, 'max': 0}
    
    async def close(self):
        """Close database connection."""
        if self._connected:
            await self.db.disconnect()
            self._connected = False
            logger.info("🔌 Integrated search system disconnected")
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        use_nl_to_sql: bool = True,
        include_metadata: bool = False,
        exclude_ids: Optional[List[int]] = None
    ) -> Any:
        """
        Search hotels using natural language query.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results to return
            use_nl_to_sql: Whether to use NL-to-SQL (True) or simple filters (False)
            include_metadata: If True, returns (results, metadata) tuple
            exclude_ids: Optional list of hotel IDs to exclude
            
        Returns:
            List of SearchResult objects or (results, metadata) tuple
        """
        if not self._connected:
            await self.connect()
        
        results = []
        metadata = {"strategy": "none"}

        # Strategy 1: Try NL-to-SQL for complex queries
        if use_nl_to_sql and self.nl_search:
            try:
                results, metadata = await self._search_with_nl_sql(query, limit)
                # Apply exclude_ids in memory for NL-to-SQL if not handled by it
                if exclude_ids and results:
                    results = [r for r in results if r.hotel_id not in exclude_ids]
                
                if results:
                    logger.info(f"✅ NL-to-SQL returned {len(results)} results")
                    return (results, metadata) if include_metadata else results
            except Exception as e:
                logger.warning(f"NL-to-SQL failed, falling back to simple search: {e}")
        
        # Strategy 2: Fall back to simple database filters
        results, metadata = await self._search_with_filters(query, limit, exclude_ids=exclude_ids)
        logger.info(f"✅ Filter search returned {len(results)} results")
        
        return (results, metadata) if include_metadata else results

    async def _search_with_nl_sql(self, query: str, limit: int) -> Tuple[List[SearchResult], Dict[str, Any]]:
        """Search using NL-to-SQL conversion."""
        if not self.nl_search:
            return [], {"error": "NL search not initialized"}
        
        # Use hybrid NL search (SQL + optional vector ranking)
        search_data = await self.nl_search.search(
            query=query,
            limit=limit,
            use_vector_reranking=self.use_vector_ranking
        )
        
        results_raw = search_data.get("results", [])
        explanation = search_data.get("explanation", "Matched via advanced query")
        
        results = [self._dict_to_result(r, match_reason=explanation) for r in results_raw]
        metadata = {
            "strategy": "nl_to_sql",
            "explanation": explanation,
            "sql": search_data.get("sql", "")
        }
        return results, metadata
    
    async def _search_with_filters(self, query: str, limit: int, exclude_ids: Optional[List[int]] = None) -> Tuple[List[SearchResult], Dict[str, Any]]:
        """Search using simple filter extraction and database query."""
        # Extract basic filters from query
        filters = self._extract_simple_filters(query)
        metadata = {"strategy": "simple_filters", "filters": filters}
        
        # Check if query contains invalid inputs that should return no results
        if filters.get('_invalid_input'):
            reason = filters.get('_invalid_reason', "Invalid input")
            logger.warning(f"Invalid input detected: {reason}")
            metadata["error"] = reason
            return [], metadata
        
        # Initial attempt
        hotels = await self.db.get_all_hotels(
            hotel_name=filters.get('hotel_name'),
            city=filters.get('city'),
            min_rating=filters.get('min_rating'),
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            amenities=filters.get('amenities'),
            exclude_city=filters.get('exclude_city'),
            exclude_amenities=filters.get('exclude_amenities'),
            exclude_ids=exclude_ids,
            limit=limit
        )

        relaxed_applied = False
        original_max_price = filters.get('max_price')
        original_min_price = filters.get('min_price')
        original_rating = filters.get('min_rating')
        original_amenities = filters.get('amenities')
        original_city = filters.get('city')

        # Smart Filter Expansion: Relax filters if no results found
        if not hotels:
            logger.info("No results with hard filters. Attempting to relax constraints...")
            
            relaxed_filters = filters.copy()
            relaxation_note = ""
            
            # 1. Try relaxing price/rating first
            if original_max_price or original_min_price or original_rating:
                # ... relaxation logic already exists ...
                # I'll just keep the existing relaxation logic but ensure it's robust
                if original_max_price:
                    # Relax price by 20%
                    relaxed_price = original_max_price * 1.2
                    relaxed_filters['max_price'] = relaxed_price
                    relaxation_note += f" (Note: Relaxed budget from ${original_max_price} to ${relaxed_price:.0f})"
                
                if original_min_price:
                    # Relax min price by 20%
                    relaxed_min_price = original_min_price * 0.8
                    relaxed_filters['min_price'] = relaxed_min_price
                    if relaxation_note: relaxation_note += " and"
                    relaxation_note += f" relaxed min price from ${original_min_price} to ${relaxed_min_price:.0f}"

                if original_rating:
                    # Relax rating by 0.5
                    relaxed_rating = max(0, original_rating - 0.5)
                    relaxed_filters['min_rating'] = relaxed_rating
                    if relaxation_note: relaxation_note += " and"
                    relaxation_note += f" relaxed rating from {original_rating} to {relaxed_rating}"

                # Try again
                hotels = await self.db.get_all_hotels(
                    hotel_name=relaxed_filters.get('hotel_name'),
                    city=relaxed_filters.get('city'),
                    min_rating=relaxed_filters.get('min_rating'),
                    min_price=relaxed_filters.get('min_price'),
                    max_price=relaxed_filters.get('max_price'),
                    amenities=relaxed_filters.get('amenities'),
                    exclude_ids=exclude_ids,
                    limit=limit
                )

            # 2. If STILL no results and we had amenities, try matching ANY amenity OR matching via vector search
            if not hotels and original_amenities:
                logger.info(f"Still no results. Dropping hard amenity filter and using vector ranking.")
                # Fetch hotels matching other criteria but ignore hard amenity check
                hotels = await self.db.get_all_hotels(
                    hotel_name=relaxed_filters.get('hotel_name'),
                    city=relaxed_filters.get('city'),
                    min_rating=relaxed_filters.get('min_rating'),
                    min_price=relaxed_filters.get('min_price'),
                    max_price=relaxed_filters.get('max_price'),
                    exclude_ids=exclude_ids,
                    limit=limit * 2 # Increase limit for vector reranking
                )
                if hotels:
                    relaxation_note += f" (Note: Broadening search to find best matches for {', '.join(original_amenities)})"
                    relaxed_applied = True
            
            # 3. If STILL no results and we had a brand/name, try dropping the city if city was extracted
            if not hotels and original_city and filters.get('hotel_name'):
                logger.info("Still no results. Trying brand/name search globally (ignoring city).")
                hotels = await self.db.get_all_hotels(
                    hotel_name=filters.get('hotel_name'),
                    exclude_ids=exclude_ids,
                    limit=limit
                )
                if hotels:
                    relaxation_note += f" (Note: Searching globally for '{filters['hotel_name']}')"
                    relaxed_applied = True

            # 2. If STILL no results and we had amenities, try matching ANY amenity (soft match)
            if not hotels and original_amenities and len(original_amenities) > 1:
                logger.info(f"Still no results. Trying partial amenity match for {original_amenities}")
                # We'll try search each amenity individually and combine, or just relax to "any"
                # Since the DB get_all_hotels uses AND, we'll do manual fetch or multiple calls
                all_partial_hotels = []
                for amen in original_amenities:
                    partial = await self.db.get_all_hotels(
                        city=relaxed_filters.get('city'),
                        min_rating=relaxed_filters.get('min_rating'),
                        max_price=relaxed_filters.get('max_price'),
                        amenities=[amen],
                        limit=limit
                    )
                    all_partial_hotels.extend(partial)
                
                # De-duplicate by ID
                seen_ids = set()
                hotels = []
                for h in all_partial_hotels:
                    if h['id'] not in seen_ids:
                        hotels.append(h)
                        seen_ids.add(h['id'])
                
                if hotels:
                    relaxation_note += f" (Note: Showing hotels with at least one of: {', '.join(original_amenities)})"
            
            if hotels:
                logger.info(f"Found {len(hotels)} results after relaxation: {relaxation_note}")
                relaxed_applied = True
                filters = relaxed_filters # Use relaxed filters for match reason
            
            # 4. FINAL FALLBACK: If still no results and we have a city + price filter, 
            # try searching globally (all cities) with the price constraint
            if not hotels and original_city and (original_min_price or original_max_price):
                logger.info(f"Still no results in {original_city}. Trying global search with price filter.")
                hotels = await self.db.get_all_hotels(
                    min_price=filters.get('min_price'),
                    max_price=filters.get('max_price'),
                    min_rating=filters.get('min_rating'),
                    amenities=filters.get('amenities'),
                    exclude_ids=exclude_ids,
                    limit=limit
                )
                if hotels:
                    price_desc = ""
                    if original_min_price:
                        price_desc = f"over ${original_min_price}"
                    elif original_max_price:
                        price_desc = f"under ${original_max_price}"
                    relaxation_note += f" (Note: No hotels found in {original_city} {price_desc}. Showing results from other cities)"
                    relaxed_applied = True
                    # Remove city from filters so the match reason is accurate
                    filters.pop('city', None)
                filters['_relaxation_note'] = relaxation_note
        
        # Apply exclusion filters in memory (Priority 2)
        if filters.get('exclude_city'):
            excluded_city = filters['exclude_city'].lower()
            hotels = [h for h in hotels if h.get('city', '').lower() != excluded_city]
            logger.info(f"Excluded city '{filters['exclude_city']}': {len(hotels)} hotels remaining")
        
        if filters.get('exclude_amenities'):
            excluded_amenities = [a.lower() for a in filters['exclude_amenities']]
            hotels = [
                h for h in hotels 
                if not any(
                    any(excl in str(ha).lower() for excl in excluded_amenities)
                    for ha in h.get('amenities', [])
                )
            ]
            logger.info(f"Excluded amenities {filters['exclude_amenities']}: {len(hotels)} hotels remaining")
        
        # Create default match reason based on filters applied
        base_match_reason = "Matched by criteria: "
        reason_parts = []
        if filters.get('city'): reason_parts.append(f"city={filters['city']}")
        if filters.get('max_price'): reason_parts.append(f"budget < ${filters['max_price']:.0f}")
        if filters.get('min_rating'): reason_parts.append(f"rating > {filters['min_rating']:.1f}")
        
        # Only add amenities to the match reason if they were actually applied and not dropped
        if filters.get('amenities') and not relaxed_applied:
            reason_parts.append(f"amenities={','.join(filters['amenities'])}")
        
        base_match_reason += ", ".join(reason_parts) if reason_parts else "Top recommendations"
        
        if relaxed_applied:
            # If relaxation happened, include the specific note which explains what changed
            base_match_reason = filters.get('_relaxation_note', 'Showing best alternatives')

        # Convert to SearchResult objects
        results = [self._dict_to_result(h, match_reason=base_match_reason) for h in hotels]
        
        # Apply vector ranking if enabled
        if self.use_vector_ranking and results:
            results = self._apply_vector_ranking(query, results)
        
        return results[:limit], metadata
    
    def _extract_simple_filters(self, query: str) -> Dict[str, Any]:
        """Extract basic filters from natural language query."""
        import re  # Import at function level to ensure it's available
        
        query_lower = query.lower()
        filters = {}
        
        # Extract city - Known valid cities in database
        # NOTE: Using cached cities for validation. If empty, uses fallback defaults.
        valid_cities = [c.lower() for c in self._available_cities] if self._available_cities else [
            'new york', 'miami', 'los angeles', 'chicago', 'san francisco',
            'boston', 'seattle', 'denver', 'portland', 'las vegas',
            'san diego', 'houston', 'dallas', 'phoenix', 'nashville',
            'philadelphia', 'minneapolis', 'new orleans', 'aspen', 'napa valley',
            'miami beach'
        ]
        
        # Extract brand/hotel name mentions
        # Common brands to check for
        brands = [
            'marriott', 'hyatt', 'hilton', 'quest', 'ibishotel', 'sofitel', 
            'crown', 'mantra', 'wrest', 'doubletree', 'ibis', 'langham', 
            'rydges', 'meriton', 'intercontinental', 'shangri-la', 'four seasons',
            'pan pacific', 'westin', 'sheraton', 'novotel', 'mercure', 'adin'
        ]
        for brand in brands:
            if brand in query_lower:
                filters['hotel_name'] = brand.title()
                break
        
        # PRIORITY 2 FIX: Check for negation patterns first
        negation_patterns = [
            r'(?:not\s+in|excluding|except|without)\s+([a-z\s]+?)(?:\s|$)',
            r'hotels?\s+(?:not|excluding)\s+([a-z\s]+)',
            r'(?:other than|besides)\s+([a-z\s]+)'
        ]
        
        # Check if query explicitly excludes a city
        negated_city = None
        for pattern in negation_patterns:
            match = re.search(pattern, query_lower)
            if match:
                potential_city = match.group(1).strip()
                # Check if the negated term is a valid city
                for city in valid_cities:
                    if city in potential_city:
                        negated_city = city
                        logger.info(f"Negation detected: Excluding city '{city}'")
                        filters['exclude_city'] = city.title()
                        break
                if negated_city:
                    break
        
        # Check for city-like patterns in query (only if no negation)
        city_patterns = [
            r'(?:hotels?|stays?|location|in|at|near)\s+(?:in|at|near)?\s*([A-Z][a-zA-Z\s]+?)(?:\s+with|\s+under|\s+rated|\?|,|$)',
            r'(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+hotels?|\s+with|\s+under|\?|$)',
        ]
        
        city_found = False
        if not negated_city:  # Only look for positive city if no negation
            for city in valid_cities:
                if city in query_lower:
                    logger.info(f"City found in query: '{city}'")
                    filters['city'] = city.title()
                    city_found = True
                    break
        
        if not city_found:
             logger.info(f"No city found in query loop. Query: '{query_lower}'")
        
        # Check if query mentions a city-like term that's not in valid list
        if not city_found:
            import re
            import difflib
            for pattern in city_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    potential_city = match.group(1).strip().lower()
                    # Common non-city words to ignore
                    ignore_words = {'the', 'a', 'an', 'with', 'and', 'or', 'all', 'some', 'many'}
                    if potential_city not in ignore_words and len(potential_city) > 3:
                        # Try fuzzy matching (Difflib)
                        close_matches = difflib.get_close_matches(potential_city, valid_cities, n=1, cutoff=0.7)
                        if close_matches:
                            corrected_city = close_matches[0]
                            logger.info(f"Fuzzy match: Corrected '{potential_city}' to '{corrected_city}'")
                            filters['city'] = corrected_city.title()
                            city_found = True
                            break
                        else:
                            # Found a city-like term that's not in our valid list
                            # SOFTENED: Don't mark as invalid immediately, just log it.
                            # Only mark invalid if it's the ONLY thing in the query and doesn't match a city.
                            if len(query.split()) < 4:
                                logger.warning(f"Invalid city detected: '{potential_city}' not in database")
                                filters['_invalid_input'] = True
                                filters['_invalid_reason'] = f"City '{potential_city}' not found in database"
                                return filters
                            else:
                                logger.info(f"Unknown location term '{potential_city}' - allowing vector search to handle it.")
                                # We don't set 'city' filter, which allow global search 
                                # (or contextual search if we injected the city in the agent)
        
        # PRIORITY 1 FIX: Extract price FIRST (before rating) to avoid conflicts
        # Price extraction with validation (handles both min and max price)
        import re
        
        # Check for price patterns first, but ensure they aren't followed by rating terms
        # Handle common then/than typo
        min_price_patterns = [
            r'(?:more\s+th[ae]n|above|over|greater\s+th[ae]n|at\s+least|starting\s+from|min|minimum)\s+(?:price|rate|budget|cost)?\s*(?:of\s+)?\$?(\d+(?:\.\d+)?)\b(?!\s*(?:star|rating|review))',
            r'\$?(\d+(?:\.\d+)?)\s*(?:\+)(?!\s*(?:star|rating|review))',
            r'\$?(\d+(?:\.\d+)?)\s*(?:dollars?|dollar)?\s*(?:and|or)\s+(?:more|above|up|higher)(?!\s*(?:star|rating|review))',
            r'\$?(\d+(?:\.\d+)?)\s*(?:plus|onwards?)(?!\s*(?:star|rating|review))'
        ]
        
        # Check for "under / less than" patterns
        max_price_patterns = [
            r'(?:under|less\s+th[ae]n|below|max|maximum|budget|cost|up\s+to)\s*(?:of\s+)?\$?(\d+(?:\.\d+)?)\b(?!\s*(?:star|rating|review))',
            r'\$?(\d+(?:\.\d+)?)\s*(?:or\s+less|and\s+under)(?!\s*(?:star|rating|review))'
        ]
        
        # General price pattern ($200) - Only match if it has $ or 'dollars'
        general_price_pattern = r'\$(\d+(?:\.\d+)?)\b(?!\s*(?:star|rating|review))|\b(\d+(?:\.\d+)?)\s*dollars?\b'

        # Try min price first
        for pattern in min_price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                price_str = match.group(1)
                price = float(price_str)
                if 0 < price < 10000:
                    filters['min_price'] = price
                break
        
        # Try max price
        for pattern in max_price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                price_str = match.group(1)
                price = float(price_str)
                if 0 <= price < 10000:
                    filters['max_price'] = price
                break
        
        # If no specific min/max found, try general pattern
        if 'min_price' not in filters and 'max_price' not in filters:
            match = re.search(general_price_pattern, query_lower)
            if match:
                price_str = match.group(1) or match.group(2)
                price = float(price_str)
                if 0 <= price < 10000:
                    filters['max_price'] = price
        
        # Validation for impossible filters (Corner Case Testing)
        if filters.get('max_price') is not None and filters['max_price'] < 10:
             # Detection for queries like "under $0" or "free hotels" (if price is indeed 0)
             # We mark as invalid to prevent relaxation from returning high-priced results
             filters['_invalid_input'] = True
             filters['_invalid_reason'] = f"Price filter '${filters['max_price']}' is too low for matching."
        
        # Rating extraction with validation (AFTER price)
        # Handles "more than 4 stars", "above 8 ratings"
        rating_patterns = [
            r'(?:rated|rating|stars?|reviews?)\s*(?:of|at|above|more\s+th[ae]n|over|at\s+least)?\s*(\d+(?:\.\d+)?)\s*(?:\+)?',
            r'(\d+(?:\.\d+)?)\s*(?:\+|star|stars|rating|ratings|reviews?)(?!\s*dollars?)',
            r'(\d+(?:\.\d+)?)\s*and\s+(?:above|up|higher)(?!\s*dollars?)'
        ]
        for pattern in rating_patterns:
            match = re.search(pattern, query_lower)
            if match:
                rating = float(match.group(1))
                if 0 <= rating <= 10:
                    filters['min_rating'] = rating
                break
        
        # Extract amenities with negation support
        amenity_keywords = {
            'pool': 'Pool',
            'gym': 'Gym',
            'wifi': 'Free Wi-Fi',
            'internet': 'Free Wi-Fi',
            'spa': 'Spa',
            'restaurant': 'Restaurant',
            'breakfast': 'breakfast included',
            'parking': 'Parking',
            'beach': 'Beach',
            'bar': 'Bar',
            'balcony': 'Balconies',
            'balconies': 'Balconies',
            'fireplace': 'Fireplace',
            'music': 'Live Music',
            'rooftop bar': 'rooftop bar',
            'pet': 'pet',
            'kitchen': 'fullyequipped kitchens',
            'laundry': 'laundry facilities'
        }
        
        # Check for excluded amenities (Priority 2)
        for keyword, amenity in amenity_keywords.items():
            # Check if amenity is negated
            negation_patterns_amenity = [
                rf'(?:without|no|not|excluding|except)\s+(?:a\s+)?{keyword}',
                rf"(?:don't|dont)\s+(?:have|want|need)\s+(?:a\s+)?{keyword}"
            ]
            is_negated = False
            for neg_pattern in negation_patterns_amenity:
                if re.search(neg_pattern, query_lower):
                    if 'exclude_amenities' not in filters:
                        filters['exclude_amenities'] = []
                    filters['exclude_amenities'].append(amenity)
                    is_negated = True
                    break
            
            # Only add as required amenity if not negated
            if not is_negated and keyword in query_lower:
                if 'amenities' not in filters:
                    filters['amenities'] = []
                filters['amenities'].append(amenity)
        
        return filters
    
    def _apply_vector_ranking(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """Apply vector similarity ranking to results."""
        if not self.embedding_model or not results:
            return results
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query, convert_to_numpy=True)
            
            # Generate embeddings for each hotel with caching (Priority 3: Performance)
            for result in results:
                # Use cached embedding if available
                cache_key = f"{result.hotel_id}_{result.hotel_name}"
                hotel_text = f"{result.hotel_name} {result.city} {result.description} {' '.join(result.amenities)}"
                hotel_full_text = hotel_text.lower()
                
                if self._embedding_cache and cache_key in self._embedding_cache:
                    hotel_embedding = self._embedding_cache[cache_key]
                else:
                    hotel_embedding = self.embedding_model.encode(hotel_text, convert_to_numpy=True)
                    
                    # Cache for future use (max 1000 entries to prevent memory bloat)
                    if self._embedding_cache is not None:
                        if len(self._embedding_cache) > 1000:
                            self._embedding_cache.clear()
                        self._embedding_cache[cache_key] = hotel_embedding
                
                # Calculate cosine similarity
                similarity = float(query_embedding @ hotel_embedding) / (
                    float((query_embedding @ query_embedding) ** 0.5) *
                    float((hotel_embedding @ hotel_embedding) ** 0.5)
                )
                result.relevance_score = similarity
                
                # Contextual Metadata Injection: Generate match reason
                match_percentage = int(similarity * 100)
                
                # HONESTY UPGRADE: Check if query terms are actually in the text
                query_terms = [t for t in query.lower().split() if len(t) > 3]
                terms_found = [t for t in query_terms if t in hotel_full_text]
                
                # If we have a relaxation note, preserve it but append similarity
                current_reason = result.match_reason or ""
                if "Note:" in current_reason:
                    result.match_reason = f"{current_reason} ({match_percentage}% semantic relevance)"
                else:
                    if match_percentage > 85 and terms_found:
                        result.match_reason = f"Excellent match for your request ({match_percentage}% relevance)"
                    elif match_percentage > 65:
                        result.match_reason = f"Good semantic match ({match_percentage}% relevance)"
                    else:
                        result.match_reason = f"Semantic match ({match_percentage}%)"
            
            # Sort by relevance score
            results.sort(key=lambda x: x.relevance_score, reverse=True)
            
        except Exception as e:
            logger.warning(f"Vector ranking failed: {e}")
        
        return results
    
    def _dict_to_result(self, hotel_dict: Dict, match_reason: Optional[str] = None) -> SearchResult:
        """Convert hotel dictionary to SearchResult object."""
        # Parse JSONB fields if they're strings
        amenities = hotel_dict.get('amenities', [])
        if isinstance(amenities, str):
            try:
                amenities = json.loads(amenities)
            except:
                amenities = []
        
        images = hotel_dict.get('images', [])
        if isinstance(images, str):
            try:
                images = json.loads(images)
            except:
                images = []
        
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

        return SearchResult(
            hotel_id=hotel_dict['id'],
            hotel_name=hotel_dict['hotel_name'],
            city=hotel_dict.get('city', 'Unknown'),
            country=hotel_dict.get('country', 'Australia'),
            description=hotel_dict.get('description') or 'A wonderful hotel with modern amenities.',
            base_price_per_night=safe_float(hotel_dict.get('base_price_per_night')),
            amenities=amenities,
            images=images,
            average_rating=safe_float(hotel_dict.get('average_rating')),
            total_ratings=safe_int(hotel_dict.get('total_ratings')),
            number_of_rooms=safe_int(hotel_dict.get('number_of_rooms')),
            room_type=hotel_dict.get('room_type', 'Standard'),
            relevance_score=hotel_dict.get('relevance_score', 1.0),
            match_reason=match_reason or hotel_dict.get('match_reason')
        )
    
    async def get_hotel_by_id(self, hotel_id: int) -> Optional[SearchResult]:
        """Get a specific hotel by ID."""
        if not self._connected:
            await self.connect()
        
        hotel = await self.db.get_hotel_by_id(hotel_id)
        return self._dict_to_result(hotel) if hotel else None
    
    async def get_available_cities(self) -> List[str]:
        """Get list of all available cities."""
        if not self._connected:
            await self.connect()
        
        return await self.db.get_cities()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._connected:
            await self.connect()
        
        return await self.db.get_stats()


async def main():
    """Demo of integrated search system."""
    print("🔍 Integrated Hotel Search System Demo\n")
    
    # Initialize search system
    search = IntegratedHotelSearch(use_vector_ranking=True)
    
    try:
        await search.connect()
        
        # Get statistics
        stats = await search.get_statistics()
        print("📊 Database Statistics:")
        print(f"   Total Hotels: {stats.get('total_hotels', 0)}")
        print(f"   Average Rating: {stats.get('avg_rating', 0):.2f}")
        print(f"   Cities: {stats.get('total_cities', 0)}")
        print(f"   Price Range: ${stats.get('min_price', 0):.0f} - ${stats.get('max_price', 0):.0f}\n")
        
        # Test queries
        test_queries = [
            "hotels in Miami with pool",
            "luxury hotels in San Francisco under $250",
            "4.5+ rated hotels with gym",
            "beach resorts in San Diego",
            "budget friendly hotels in New York"
        ]
        
        for query in test_queries:
            print(f"🔍 Query: '{query}'")
            results = await search.search(query, limit=3, use_nl_to_sql=False)
            
            if results:
                for i, hotel in enumerate(results, 1):
                    print(f"   {i}. {hotel.hotel_name} ({hotel.city})")
                    print(f"      ${hotel.base_price_per_night:.0f}/night | ⭐{hotel.average_rating:.2f} ({hotel.total_ratings} reviews)")
                    print(f"      Amenities: {', '.join(hotel.amenities[:3])}")
                    if search.use_vector_ranking:
                        print(f"      Relevance: {hotel.relevance_score:.3f}")
            else:
                print("   No results found")
            print()
        
    finally:
        await search.close()


if __name__ == "__main__":
    asyncio.run(main())
