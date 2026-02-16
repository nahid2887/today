"""
Hybrid Search Engine combining SQL-like filters with Vector Semantic Search.

Architecture:
1. Parse natural language query → Extract hard filters
2. Apply hard filters to vector metadata (city, price, room_type)
3. Perform semantic search on filtered subset
4. Rank results using hybrid scoring
5. Return top N with pagination support
"""
import logging
from typing import List, Dict, Any, Optional
from core.vector_store import VectorManager
from core.query_parser import QueryParser, SearchFilters
from config import RATING_WEIGHT, SIMILARITY_WEIGHT, TOP_K_RESULTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search combining structured filters with semantic search.
    
    Implements the architecture:
    - 1a. Hard Filters (SQL-like) on metadata
    - 1b. Semantic Search (Vector similarity)
    - 2. Hybrid Merger with scoring
    - 3. Pagination support
    """
    
    def __init__(self, vector_manager: VectorManager):
        """
        Initialize hybrid search engine.
        
        Args:
            vector_manager: VectorManager instance for vector operations
        """
        self.vector_manager = vector_manager
        self.query_parser = QueryParser()
        logger.info("HybridSearchEngine initialized")
    
    def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 3,
        k_candidates: int = 10
    ) -> Dict[str, Any]:
        """
        Perform hybrid search on hotels.
        
        Args:
            query: Natural language search query
            offset: Pagination offset
            limit: Number of results to return
            k_candidates: Number of candidates to retrieve from vector search
            
        Returns:
            Dictionary containing:
            - results: List of hotel dictionaries
            - filters: Applied filters
            - total: Total matching hotels
            - offset: Current offset
            - limit: Results per page
            - has_more: Boolean indicating if more results exist
        """
        # 1. Parse query into filters + semantic query
        filters = self.query_parser.parse(query)
        
        logger.info(f"Search query: {query}")
        logger.info(f"Parsed filters: {filters.to_dict()}")
        logger.info(f"Semantic query: {filters.semantic_query}")
        
        # 2. Perform vector search with metadata filters
        search_query = filters.semantic_query or query
        vector_results = self.vector_manager.search_hotels(
            query=search_query,
            city=filters.city,
            k=k_candidates
        )
        
        logger.info(f"Vector search returned {len(vector_results)} candidates")
        
        # 3. Apply additional filters (price, rating, amenities, room_type)
        filtered_results = self._apply_hard_filters(vector_results, filters)
        
        logger.info(f"After hard filters: {len(filtered_results)} hotels")
        
        # 4. Rank results using hybrid scoring
        ranked_results = self._rank_results(filtered_results, filters)
        
        # 5. Apply pagination
        total = len(ranked_results)
        paginated_results = ranked_results[offset:offset + limit]
        
        logger.info(f"Returning {len(paginated_results)} results (offset={offset}, limit={limit})")
        
        return {
            "results": paginated_results,
            "filters": {
                "city": filters.city,
                "price_min": filters.price_min,
                "price_max": filters.price_max,
                "amenities": filters.amenities,
                "room_type": filters.room_type,
                "min_rating": filters.min_rating,
                "max_rating": filters.max_rating,
            },
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total,
            "semantic_query": filters.semantic_query
        }
    
    def _apply_hard_filters(
        self,
        results: List[Dict[str, Any]],
        filters: SearchFilters
    ) -> List[Dict[str, Any]]:
        """
        Apply hard filters to vector search results.
        
        Filters:
        - Price range
        - Minimum rating
        - Maximum rating
        - Amenities (partial match)
        - Room type
        """
        filtered = []
        
        for hotel in results:
            # Price filter (if we have price data)
            if filters.price_max is not None:
                # Price is not in vector metadata, would need live API call
                # For now, skip hotels without price info
                pass
            
            # Rating filters
            hotel_rating = hotel.get("average_rating", 0.0)
            
            if filters.min_rating is not None:
                if hotel_rating < filters.min_rating:
                    logger.debug(f"Filtered out {hotel.get('hotel_name')}: "
                               f"rating {hotel_rating} < {filters.min_rating}")
                    continue
            
            if filters.max_rating is not None:
                if hotel_rating > filters.max_rating:
                    logger.debug(f"Filtered out {hotel.get('hotel_name')}: "
                               f"rating {hotel_rating} > {filters.max_rating}")
                    continue
            
            # Room type filter (case-insensitive)
            if filters.room_type:
                hotel_room_type = str(hotel.get("room_type", "")).lower()
                if filters.room_type.lower() not in hotel_room_type:
                    logger.debug(f"Filtered out {hotel.get('hotel_name')}: "
                               f"room_type {hotel_room_type} != {filters.room_type}")
                    continue
            
            # Amenities filter (partial match - hotel should have ALL requested amenities)
            if filters.amenities:
                hotel_amenities_str = str(hotel.get("amenities", "")).lower()
                
                # Check if hotel has all requested amenities
                # Use flexible matching: "pool" matches "Pool", "Swimming Pool", "pool access", etc.
                has_all_amenities = True
                for amenity in filters.amenities:
                    amenity_lower = amenity.lower()
                    
                    # Check if any word from the amenity appears in hotel amenities
                    # This handles "pool" matching "Pool" or "Swimming Pool"
                    if amenity_lower not in hotel_amenities_str:
                        has_all_amenities = False
                        logger.debug(f"Filtered out {hotel.get('hotel_name')}: "
                                   f"missing amenity '{amenity}' (hotel has: {hotel_amenities_str})")
                        break
                
                if not has_all_amenities:
                    continue
            
            filtered.append(hotel)
        
        return filtered
    
    def _rank_results(
        self,
        results: List[Dict[str, Any]],
        filters: SearchFilters
    ) -> List[Dict[str, Any]]:
        """
        Rank results using hybrid scoring.
        
        Score = (RATING_WEIGHT × normalized_rating) + (SIMILARITY_WEIGHT × similarity)
        
        Already sorted by similarity from vector search, but we refine with ratings.
        """
        for hotel in results:
            rating = hotel.get("average_rating", 0.0)
            similarity = hotel.get("similarity_score", 0.0)
            
            # Normalize rating to 0-1 scale
            normalized_rating = float(rating) / 5.0
            
            # Calculate hybrid score
            hybrid_score = (
                RATING_WEIGHT * normalized_rating +
                SIMILARITY_WEIGHT * similarity
            )
            
            hotel["hybrid_score"] = hybrid_score
            hotel["normalized_rating"] = normalized_rating
        
        # Sort by hybrid score (descending)
        results.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
        
        return results
    
    def get_hotel_by_id(self, hotel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get hotel by ID from vector store.
        
        Args:
            hotel_id: Hotel ID
            
        Returns:
            Hotel dictionary or None if not found
        """
        # This would require a get_by_id method in VectorManager
        # For now, we'll need to implement this in VectorManager
        logger.warning("get_hotel_by_id not yet implemented")
        return None
