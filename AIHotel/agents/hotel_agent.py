"""
Hotel Recommendation Agent using LangGraph State Machine.

This module implements a multi-stage agentic workflow:
1. Search: Hybrid city filter + semantic search
2. Ranker: Score results using rating and similarity
3. Response: Generate natural language response from DB data
"""
import logging
import re
import json
import time
from typing import Dict, Any, List, TypedDict, Annotated, Optional
from operator import add

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from core.integrated_search import IntegratedHotelSearch
from tools.tavily_hotel_search import TavilyHotelSearch
from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_MODEL_FAST,
    RATING_WEIGHT,
    SIMILARITY_WEIGHT,
    TOP_K_RESULTS,
    TAVILY_API_KEY
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """
    State definition for the LangGraph state machine.
    
    Attributes:
        query: User's natural language query
        history: Conversation history
        extracted_city: Extracted city from query
        search_results: Raw search results from vector store
        ranked_hotels: Hotels ranked by score
        hydrated_hotels: Hotels with live data
        response: Natural language response
        error: Any error messages
        shown_hotel_ids: Set of hotel IDs already shown in this session
        pagination_offset: Current offset for pagination
        filters_applied: Parsed filters from query
    """
    query: str
    history: List[Dict[str, str]]
    extracted_city: str
    search_results: List[Dict[str, Any]]
    ranked_hotels: List[Dict[str, Any]]
    hydrated_hotels: List[Dict[str, Any]]
    response: str
    error: str
    shown_hotel_ids: List[int]  # Track shown hotels
    pagination_offset: int  # Track pagination
    filters_applied: Dict[str, Any]  # Store applied filters
    last_hotels: List[Dict[str, Any]]  # Memory: Hotels from previous turn
    is_refinement: bool  # Flag if current query is a refinement of previous results
    is_external_search: bool  # Flag: results came from Tavily, not the DB


class HotelRecommendationAgent:
    """
    Main agent for hotel recommendations using LangGraph orchestration.
    
    This agent implements a three-stage workflow:
    - Stage 1 (Search): Performs hybrid search with city filtering
    - Stage 2 (Ranker): Ranks results using weighted scoring
    - Stage 3 (Hydrator): Enriches top results with live data
    """
    
    def __init__(self, search_system: IntegratedHotelSearch):
        """
        Initialize the hotel recommendation agent.
        
        Args:
            search_system: Instance of IntegratedHotelSearch for database queries
        """
        self.search_system = search_system
        
        # Initialize LLM (Groq)
        if not GROQ_API_KEY:
            raise ValueError("No GROQ_API_KEY found. Set GROQ_API_KEY environment variable.")

        # Main LLM: used ONLY for final natural language response generation.
        # Uses llama-3.3-70b-versatile (100K TPD free) — keep usage minimal.
        self.llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL,
            temperature=0.3,
            max_tokens=512   # 2-3 sentence responses; 512 is plenty and halves token spend
        )
        # Fast LLM: used for ALL cheap calls (query correction, city extraction).
        # Uses llama-3.1-8b-instant (500K TPD free) — 5× the daily headroom.
        self.llm_fast = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL_FAST,
            temperature=0.0,
            max_tokens=80
        )
        self.llm_provider = "Groq"
        logger.info(f"Using Groq models: {GROQ_MODEL} (response) / {GROQ_MODEL_FAST} (fast)")
        
        # Initialize Tavily external search fallback
        if TAVILY_API_KEY:
            self.tavily_search = TavilyHotelSearch(
                tavily_api_key=TAVILY_API_KEY,
                groq_api_key=GROQ_API_KEY,
                groq_model=GROQ_MODEL_FAST   # use fast model for JSON extraction
            )
            if self.tavily_search.available:
                logger.info("Tavily external hotel search: ENABLED")
            else:
                logger.warning("Tavily client unavailable (tavily-python not installed)")
        else:
            self.tavily_search = None
            logger.info("Tavily external hotel search: DISABLED (no API key)")
        
        # Build the state machine graph
        # NOTE: The compiled graph is not directly invoked because run() 
        # needs to mix async and sync node calls. Nodes are called manually.
        self.graph = self._build_graph()
        
        logger.info("HotelRecommendationAgent initialized with IntegratedHotelSearch")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state machine.
        
        Returns:
            Compiled state graph
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("search", self._search_node)
        workflow.add_node("rank", self._rank_node)
        workflow.add_node("hydrate", self._hydrate_node)
        workflow.add_node("generate_response", self._generate_response_node)
        
        # Define edges
        workflow.set_entry_point("search")
        workflow.add_edge("search", "rank")
        workflow.add_edge("rank", "hydrate")
        workflow.add_edge("hydrate", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()

    @staticmethod
    def _parse_groq_wait(err_str: str) -> float:
        """
        Parse Groq's suggested retry delay from a 429 error string.
        Handles: '6m30.527s' → 390.5s,  '45.3s' → 45.3s
        """
        m = re.search(r'try again in (\d+)m(\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
        if m:
            return int(m.group(1)) * 60 + float(m.group(2))
        m = re.search(r'try again in (\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 60.0

    @staticmethod
    def _is_tpd(err_str: str) -> bool:
        """Return True if this 429 is a daily quota exhaustion (TPD).
        TPD resets in ~24h — retrying the same session is pointless.
        TPM (per-minute) is transient and worth retrying."""
        el = err_str.lower()
        return ('tokens per day' in el or
                '(tpd)' in el or
                'per day' in el)

    def _llm_invoke_with_retry(self, llm, messages, max_retries: int = 2):
        """
        Invoke an LLM with retry only for TPM (per-minute) rate limits.
        TPD (daily quota) is raised immediately — waiting doesn't help.
        TPM retries are capped at 90 seconds to keep UX responsive.
        """
        for attempt in range(max_retries):
            try:
                return llm.invoke(messages)
            except Exception as e:
                err_str = str(e)
                is_rate_limit = ('429' in err_str or
                                 'rate_limit' in err_str.lower() or
                                 'rate limit' in err_str.lower() or
                                 'tokens per' in err_str.lower())
                if is_rate_limit:
                    if self._is_tpd(err_str):
                        # Daily quota gone — retrying is useless, surface immediately
                        logger.warning(
                            "[RATE LIMIT] Groq daily token quota (TPD) exhausted. "
                            "Will not retry. Resets in ~24h."
                        )
                        raise
                    # TPM — per-minute limit, brief wait then retry once
                    if attempt < max_retries - 1:
                        wait_sec = min(self._parse_groq_wait(err_str) + 3.0, 90.0)
                        logger.warning(
                            f"[RATE LIMIT] Groq TPM limit. "
                            f"Pausing {wait_sec:.0f}s before retry {attempt + 2}/{max_retries}..."
                        )
                        time.sleep(wait_sec)
                        continue
                raise
        raise RuntimeError("LLM max retries exceeded")

    def _extract_city_from_query(self, query: str, history: List[Dict[str, str]]) -> str:
        """
        Extract city name from user query using LLM and recent history.
        
        Args:
            query: User's query
            history: Conversation history
            
        Returns:
            Extracted city name or empty string
        """
        try:
            # Format recent history for context
            history_context = ""
            if history:
                recent = history[-4:] # Last 2 pairs
                for msg in recent:
                    role = "User" if msg['role'] == 'user' else "Assistant"
                    history_context += f"{role}: {msg['content']}\n"

            prompt = f"""Extract the city name from the following query. 
Use the provided conversation history to resolve pronouns like "there", "that city", or "that place".

Conversation History:
{history_context}

User Query: {query}

If no city is mentioned and cannot be inferred from history, return "ANY".
Only return the city name, nothing else.

City:"""
            
            # City extraction only needs 1-3 words output — use fast model
            response = self._llm_invoke_with_retry(self.llm_fast, [HumanMessage(content=prompt)])
            city = response.content.strip().strip('"')
            
            if city.upper() == "ANY" or not city:
                return ""
            
            logger.info(f"Extracted city: {city}")
            return city
            
        except Exception as e:
            logger.error(f"Error extracting city: {e}")
            return ""
    
    async def _search_node_async(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 1: Perform database search with filters and session tracking.
        
        Uses IntegratedHotelSearch to query database with natural language.
        Now supports "refinement" queries to filter within previous turn results.
        """
        query = state['query']
        query_lower = query.lower()
        last_hotels = state.get('last_hotels', [])
        
        logger.info(f"[SEARCH NODE] Processing query: {query}")
        
        # Check if this is a refinement query (e.g., "cheapest", "best rating")
        refinement_keywords = ["cheaper", "cheapest", "better", "best", "more reviews", "first", "second", "third", "which one", "instead", "another", "else", "those", "them", "these", "they", "also", "still", "only", "about"]
        is_refinement = any(f" {kw} " in f" {query_lower} " or query_lower.startswith(f"{kw} ") or query_lower == kw for kw in refinement_keywords) and len(last_hotels) > 0
        
        # PERSIST CITY CONTEXT: If no city in current query, but previous query had one
        prev_city = ""
        if last_hotels:
            prev_city = last_hotels[0].get('city', "")
        
        if is_refinement:
            logger.info(f"Refining within {len(last_hotels)} previous results")
            # If no city info is in the query, inject the previous city to help the search system
            if prev_city and " in " not in query_lower and " at " not in query_lower:
                logger.info(f"Injecting previous city context: {prev_city}")
                query = f"{query} in {prev_city}"
            
            # Note: We NO LONGER return early here. We allow the search system to 
            # re-query with the new constraints (like "pool") but within the same context.
            # This enables "Do any of them have a pool?" to work correctly.

        # SMART QUERY CORRECTION & CONTEXT RESOLUTION
        # Skip if orchestrator already resolved the query in its classify step
        if state.get('skip_query_correction'):
            logger.info("[SEARCH] Skipping query correction (orchestrator already resolved)")
        else:
            try:
                available_cities = await self.search_system.get_available_cities()
                if available_cities:
                    cities_str = ", ".join(available_cities)
                    
                    # Format recent history for query resolution
                    history_context = ""
                    if state.get('history'):
                        recent = state['history'][-4:]
                        for msg in recent:
                            role = "User" if msg['role'] == 'user' else "Assistant"
                            history_context += f"{role}: {msg['content']}\n"

                    correction_prompt = f"""You are a helpful travel assistant. 
The user is searching for hotels. We have the following cities in our database: {cities_str}

Analyze the user's query and the conversation history to produce a standalone, corrected search query.

CRITICAL RULES:
1. Correct city name typos (e.g., "Parth" -> "Perth", "cumilla" -> "Comilla").
2. ONLY carry over location context if the query has EXPLICIT references:
   - Pronouns: "they", "them", "those", "these"
   - Location words: "there", "that city", "that place", "same place"
   - Examples: "do THEY have pool?" -> carry over city
   - Examples: "hotels with pool" -> DO NOT carry over city (no explicit reference)
3. PRESERVE CONSTRAINTS from previous queries IF the new query is a refinement:
   - If user said "under $200" and now says "which are best rated?", keep budget constraint
   - If user said "hotels with pool" and now says "cheapest one", keep pool requirement
4. OUTPUT ONLY THE SEARCH QUERY - no explanations, no reasoning, just the query.
5. DO NOT list specific hotel names unless user mentions them.

Examples:
User Query: "peaceful pool hotels" (previous: "perth luxury hotels")
Output: Hotels with a pool

User Query: "do any of them have a pool?" (previous: showing Sydney hotels)
Output: Hotels with a pool in Sydney

User Query: "show me cheaper ones" (previous: "hotels in Melbourne under $300")
Output: Hotels in Melbourne under $300

User Query: "hotels more than 200 dollars" (previous: "hotels in Sydney")
Output: Hotels over $200

Conversation History:
{history_context}

User's Latest Query: "{query}"

OUTPUT (query only, no explanation):"""
                    
                    # Use a cheap low-token LLM for this short correction call
                    correction_response = self._llm_invoke_with_retry(self.llm_fast, [HumanMessage(content=correction_prompt)])
                    raw_response = correction_response.content.strip()
                    
                    # Extract query - LLM should return just the query now
                    # But check for old format markers just in case
                    if "STANDALONE CORRECTED QUERY:" in raw_response:
                        corrected_query = raw_response.split("STANDALONE CORRECTED QUERY:")[-1].strip()
                    elif "OUTPUT:" in raw_response:
                        corrected_query = raw_response.split("OUTPUT:")[-1].strip()
                    else:
                        # Use entire response (should just be the query)
                        corrected_query = raw_response
                    
                    # Clean up quotes and extra whitespace
                    corrected_query = corrected_query.strip('"').strip("'").strip()
                    
                    if corrected_query.lower() != query.lower():
                        logger.info(f"LLM resolved context: '{query}' -> '{corrected_query}'")
                        query = corrected_query
            except Exception as e:
                logger.warning(f"Query resolution skipped: {e}")

        try:
            # Never exclude previously shown hotels - always show all matching results
            results, metadata = await self.search_system.search(
                query=query,
                limit=10,
                use_nl_to_sql=False,
                include_metadata=True,
                exclude_ids=[]
            )
            
            # Check for specific validation errors from the search system
            if metadata.get('error'):
                logger.warning(f"Search system reported error: {metadata['error']}")
                return {
                    **state,
                    "search_results": [],
                    "filters_applied": metadata.get('filters', {}),
                    "error": f"Invalid input: {metadata['error']}"
                }

            # Convert SearchResult objects to dicts
            hotel_dicts = []
            for result in results:
                hotel_dict = {
                    'id': result.hotel_id,
                    'hotel_name': result.hotel_name,
                    'city': result.city,
                    'country': result.country,
                    'description': result.description,
                    'base_price_per_night': result.base_price_per_night,
                    'amenities': result.amenities,
                    'images': result.images,
                    'average_rating': result.average_rating,
                    'total_ratings': result.total_ratings,
                    'room_type': result.room_type,
                    'number_of_rooms': result.number_of_rooms,
                    'similarity_score': result.relevance_score,
                    'match_reason': result.match_reason
                }
                hotel_dicts.append(hotel_dict)
            
            if not hotel_dicts:
                logger.warning("No hotels found matching criteria")
                return {
                    **state,
                    "search_results": [],
                    "filters_applied": metadata.get('filters', {}),
                    "error": "No hotels found matching your criteria."
                }
            
            logger.info(f"Found {len(hotel_dicts)} hotels from database")
            
            return {
                **state,
                "search_results": hotel_dicts,
                "filters_applied": metadata.get('filters', {}),
                "is_refinement": is_refinement,
                "error": ""
            }
            
        except Exception as e:
            logger.error(f"Search node error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "error": f"Search failed: {str(e)}",
                "search_results": []
            }
    
    def _search_node(self, state: AgentState) -> Dict[str, Any]:
        """Sync wrapper for search node."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create task for async execution
                import nest_asyncio
                nest_asyncio.apply()
        except:
            pass
        
        return asyncio.get_event_loop().run_until_complete(self._search_node_async(state))

    def _tavily_fallback_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Fallback Node: Search externally via Tavily when the DB has no results.

        Triggered when:
          - _search_node returned 0 results (unknown city, unsupported amenity, etc.)
          - TavilyHotelSearch is available

        Returns hotels in the same schema as DB hotels, plus:
          source = "external"
          booking_url = direct link to hotel on booking site
          disclaimer = user-facing warning that this is an external result
        """
        query = state.get('query', '')
        filters_applied = state.get('filters_applied', {})
        original_error = state.get('error', '')

        city = None
        # Try to get city from the extracted filter (set during _search_node)
        if filters_applied.get('city'):
            city = filters_applied['city']
        # Also try to harvest from the unknown-city metadata
        elif filters_applied.get('_unknown_city_name'):
            city = filters_applied['_unknown_city_name']

        logger.info(f"[TAVILY FALLBACK] DB returned 0 results. Searching externally for: city={city}, query='{query}'")

        try:
            # Strip internal filter keys before passing to Tavily
            clean_filters = {
                k: v for k, v in filters_applied.items()
                if not k.startswith('_')
            }
            hotels = self.tavily_search.search(
                query=query,
                city=city,
                filters=clean_filters,
                max_results=5
            )

            if not hotels:
                logger.info("[TAVILY FALLBACK] No external results either.")
                return {
                    **state,
                    "search_results": [],
                    "is_external_search": False,
                    "error": original_error or "No hotels found for this location."
                }

            # Filter out 0-rated hotels (same quality bar as the DB filter)
            rated_hotels = [h for h in hotels if h.get('average_rating', 0) > 0]
            if rated_hotels:
                hotels = rated_hotels
            # else keep all (every hotel was unrated) — better than empty results

            # Apply min_rating filter from user query (Tavily may return lower-rated hotels)
            min_rating = clean_filters.get('min_rating')
            if min_rating is not None:
                filtered = [h for h in hotels if h.get('average_rating', 0) >= min_rating]
                if filtered:
                    hotels = filtered
                    logger.info(f"[TAVILY FALLBACK] Applied min_rating={min_rating} filter: {len(hotels)} hotels remain")

            # Apply max_rating filter
            max_rating = clean_filters.get('max_rating')
            if max_rating is not None:
                filtered = [h for h in hotels if h.get('average_rating', 0) < max_rating]
                if filtered:
                    hotels = filtered

            # Price-aware sorting for budget / luxury / max-price queries
            query_lower = query.lower()
            budget_keywords = ['cheap', 'budget', 'affordable', 'inexpensive', 'low cost']
            luxury_keywords = ['luxury', 'premium', 'upscale', 'expensive', '5 star', 'five star']
            if any(kw in query_lower for kw in budget_keywords) or clean_filters.get('max_price'):
                # Sort cheapest first; push hotels with no price to end
                hotels.sort(key=lambda h: (
                    h.get('base_price_per_night') is None,
                    h.get('base_price_per_night') or float('inf')
                ))
            elif any(kw in query_lower for kw in luxury_keywords) or clean_filters.get('min_price'):
                # Sort most expensive first; push hotels with no price to end
                hotels.sort(key=lambda h: (
                    h.get('base_price_per_night') is None,
                    -(h.get('base_price_per_night') or 0)
                ))

            logger.info(f"[TAVILY FALLBACK] Found {len(hotels)} external hotels")
            return {
                **state,
                "search_results": hotels,
                "is_external_search": True,
                "error": ""   # clear the DB error — we have results now
            }

        except Exception as e:
            logger.error(f"[TAVILY FALLBACK] Error: {e}")
            return {
                **state,
                "search_results": [],
                "is_external_search": False,
                "error": original_error or str(e)
            }

    def _rank_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 2: Rank search results.
        
        Uses the formula: Score = (0.6 * average_rating) + (0.4 * semantic_similarity)
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with ranked_hotels (top 3)
        """
        logger.info("[RANK NODE] Ranking hotels")
        
        try:
            search_results = state.get('search_results', [])
            query_lower = state.get('query', '').lower()
            is_refinement = state.get('is_refinement', False)
            
            if not search_results:
                return {
                    **state,
                    "ranked_hotels": []
                }
            
            def _get_price(h):
                p = h.get('base_price_per_night') or h.get('price')
                return float(p) if p else 999999.0

            budget_kws = ["cheap", "budget", "affordable", "inexpensive", "low cost", "economy"]
            luxury_kws = ["luxury", "premium", "upscale", "5 star", "five star", "expensive"]
            is_budget_query = any(kw in query_lower for kw in budget_kws)
            is_luxury_query = any(kw in query_lower for kw in luxury_kws)

            # Special handling for refinement queries
            if is_refinement:
                if any(kw in query_lower for kw in ["cheap", "price", "low"]):
                    # Sort by price ascending
                    logger.info("Sorting by price (ascending) for refinement")
                    ranked = sorted(search_results, key=_get_price)
                    return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}
                
                if any(kw in query_lower for kw in ["rating", "best", "review", "top"]):
                    # Sort by rating descending
                    logger.info("Sorting by rating (descending) for refinement")
                    ranked = sorted(search_results, key=lambda x: x.get('average_rating', 0), reverse=True)
                    return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}

            # Price-aware sorting for budget/luxury initial queries
            if is_budget_query:
                logger.info("Sorting by price (ascending) for budget query")
                ranked = sorted(search_results, key=_get_price)
                return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}
            if is_luxury_query:
                logger.info("Sorting by price (descending) for luxury query")
                ranked = sorted(search_results, key=lambda h: -_get_price(h) if _get_price(h) != 999999.0 else 0)
                return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}

            # Default: Calculate composite score for each hotel
            scored_hotels = []
            for hotel in search_results:
                # Normalize average_rating - Database consistently uses a 10.0 scale
                raw_rating = hotel.get('average_rating', 0.0)
                # Hotels with 0 rating are incomplete records — use true 0 so they sink to bottom
                normalized_rating = raw_rating / 10.0
                
                # Similarity score is already normalized (0-1)
                similarity = hotel.get('similarity_score', 0.5)
                
                # Calculate weighted score (0.8 rating + 0.2 similarity)
                # Rating is the dominant factor; similarity breaks ties between close-rated hotels
                composite_score = (RATING_WEIGHT * normalized_rating) + (SIMILARITY_WEIGHT * similarity)
                hotel_with_score = hotel.copy()
                
                hotel_with_score['composite_score'] = composite_score
                scored_hotels.append(hotel_with_score)
            
            # Sort by composite score (descending)
            ranked = sorted(scored_hotels, key=lambda x: x['composite_score'], reverse=True)
            
            # Take top K results
            top_hotels = ranked[:TOP_K_RESULTS]
            
            logger.info(f"Ranked top {len(top_hotels)} hotels")
            for i, hotel in enumerate(top_hotels, 1):
                logger.info(
                    f"  {i}. {hotel.get('hotel_name')} - "
                    f"Score: {hotel['composite_score']:.3f} "
                    f"(Rating: {hotel.get('average_rating', 0):.2f}, "
                    f"Similarity: {hotel.get('similarity_score', 0):.3f})"
                )
            
            return {
                **state,
                "ranked_hotels": top_hotels
            }
            
        except Exception as e:
            logger.error(f"Rank node error: {e}")
            return {
                **state,
                "ranked_hotels": state.get('search_results', [])[:TOP_K_RESULTS],
                "error": f"Ranking failed: {str(e)}"
            }
    
    async def _hydrate_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node 3: Hydrate top hotels with live data.
        
        Fetches real-time pricing, offers, and availability for the top-ranked hotels.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with hydrated_hotels
        """
        logger.info("[HYDRATE NODE] Using DB data directly (live API disabled)")
        ranked_hotels = state.get('ranked_hotels', [])
        logger.info(f"Passing through {len(ranked_hotels)} hotels from DB")
        return {
            **state,
            "hydrated_hotels": ranked_hotels
        }
    
    def _generate_response_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Final Node: Generate natural language response designed for the UI.
        """
        logger.info("[GENERATE RESPONSE NODE] Creating persuasive response")
        
        try:
            hydrated_hotels = state.get('hydrated_hotels', [])
            query = state.get('query', '')
            error = state.get('error', '')
            is_external = state.get('is_external_search', False)
            
            # 1. Handle Errors for UI
            if error and not hydrated_hotels:
                # City-not-found: give a specific helpful message with available cities
                if 'have hotels in' in error or 'currently have hotels' in error:
                    clean_err = error.replace('Invalid input: ', '')
                    return {
                        **state,
                        "response": f"Sorry, {clean_err} Try searching for one of those instead!"
                    }
                return {
                    **state,
                    "response": f"I couldn't find any hotels matching those criteria. Could you try adjusting your search terms?"
                }
            
            if not hydrated_hotels:
                return {
                    **state,
                    "response": "I couldn't find any hotels matching those exact details. Why not try a broader search or a different city?"
                }
            
            # 2. Enrich hotels with UI-friendly fields (Help Frontend)
            # We add fields like 'badges', 'perks', and 'formatted_price'
            requested_amenities = state.get('filters_applied', {}).get('amenities', [])
            amenities_found_anywhere = set()
            
            for idx, hotel in enumerate(hydrated_hotels):
                # Real amenities from DB
                hotel_amenities = hotel.get('amenities', [])
                if isinstance(hotel_amenities, str):
                    try:
                        hotel_amenities = json.loads(hotel_amenities)
                    except:
                        hotel_amenities = []
                
                # Perks: Combine special offers with requested amenities if present
                perks = hotel.get('special_offers', [])
                if not isinstance(perks, list): perks = []
                
                description = (hotel.get('description') or '').lower()
                
                # If user asked for something specific (e.g. Gym), check amenities OR description
                for req in requested_amenities:
                    req_lower = req.lower()
                    # Check in explicit tags
                    found = next((a for a in hotel_amenities if req_lower in a.lower()), None)
                    if found:
                        if found not in perks: perks.append(found)
                        amenities_found_anywhere.add(req)
                    else:
                        # Check in description
                        if req_lower in description:
                            # Add a nice looking perk based on the request
                            perk_name = req.capitalize()
                            if perk_name not in perks:
                                perks.append(f"{perk_name} (in-house)")
                            amenities_found_anywhere.add(req)

                # Fallback perks if still empty - use actual amenities from hotel data
                if not perks:
                    real_amenities = hotel.get('amenities', [])
                    if isinstance(real_amenities, list) and real_amenities:
                        perks = real_amenities[:3]
                    else:
                        perks = []
                
                hotel['perks'] = perks[:3] # Keep UI clean
                
                # Only add badges if they actually exist in the data
                if 'badges' not in hotel:
                    hotel['badges'] = []
                
                # Image fallback - leave empty if no real images
                if not hotel.get('images'):
                    hotel['images'] = []

            # 3. Build context for enthusiastic LLM response
            # Note if some requested amenities are missing
            missing_amenities = [a for a in requested_amenities if a not in amenities_found_anywhere]
            missing_info = ""
            if missing_amenities:
                missing_info = f"\nIMPORTANT: None of the results have confirmed {', '.join(missing_amenities)}. Inform the user honestly."

            # Format history for conversational flow
            history_context = ""
            if state.get('history'):
                recent = state['history'][-4:] # Last 2 pairs
                for msg in recent:
                    role = "User" if msg['role'] == 'user' else "Assistant"
                    history_context += f"{role}: {msg['content']}\n"

            hotels_context = []
            for i, hotel in enumerate(hydrated_hotels, 1):
                rating = hotel.get('average_rating', 0.0)
                amenities_str = ", ".join(hotel.get('perks', []))
                match_reason = hotel.get('match_reason', '')
                
                # Include a relevant snippet of the description if it matches the query
                desc_snippet = ""
                description = hotel.get('description') or ""
                if requested_amenities:
                    # Try to find a sentence with the requested amenity
                    for req in requested_amenities:
                        match = re.search(f"[^.!?]*{req}[^.!?]*", description, re.IGNORECASE)
                        if match:
                            desc_snippet = f" Highlights: \"{match.group(0).strip()}...\""
                            break
                
                # Include booking_url for external hotels so LLM can reference it
                booking_url = hotel.get('booking_url', '')
                booking_note = f" Book at: {booking_url}" if booking_url else ""
                summary = f"- {hotel.get('hotel_name')} (Rating: {rating}/10): {match_reason}. Amenities: {amenities_str}.{desc_snippet}{booking_note}"
                hotels_context.append(summary)
            
            hotels_text = "\n".join(hotels_context)
            
            # Use standard string and .format() to avoid f-string escaping confusion
            count = len(hydrated_hotels)

            # Build external search instruction block
            if is_external:
                external_instruction = """\nEXTERNAL RESULTS NOTICE:
- These hotels were found via a web search because we do not have hotels in this destination in our partner database.
- They are NOT bookable through our platform.
- Acknowledge warmly that we found external options for the user.
- Each hotel entry in 'Found Hotels' below may include a "Book at: <url>" field.
  Use that EXACT URL when mentioning booking links. Do NOT write "[booking_url]" or any placeholder.
  If no URL is provided for a hotel, simply say "book directly on their website".
- Always close with: "Please note these are external results — not in our partner network. Book directly via the links provided."
"""
            else:
                external_instruction = ""

            system_prompt_template = """You are an expert travel concierge.
Your goal is to generate a warm, persuasive, and helpful response for the user's chat bubble.

CRITICAL RULES — NEVER break these:
- NEVER invent, assume, or hallucinate hotel names, cities, ratings, prices, or amenities.
- ONLY reference the hotels EXACTLY as listed below under 'Found Hotels (Contextual Facts)'.
- If a hotel is in Perth, say it is in Perth. Do NOT say it is in Sydney, Melbourne, or any other city.
- The rating values below are from a live database — use them exactly as given (e.g. "4.8/10").
{external_instruction}
Style Guidelines:
- Use the Conversation History to maintain a natural flow (e.g., "Following up on that," or "As you mentioned...").
- Start with an enthusiastic opening.
- Mention the number of hotels found ({count} hotels) and what city they are in.
- Be positive and direct. Do NOT hedge, apologize, or add disclaimers unless the hotels
  genuinely could not match (e.g., city not in database, explicit amenity missing).
- "Semantic match" in the Contextual Facts is NORMAL — it just means vector search was used.
  Do NOT tell the user results are "closest alternatives" or "potential matches" for a normal search.
- ONLY mention missing amenities if {missing_info} is non-empty. Otherwise stay positive.
- For ratings, always use a 10-point scale (e.g., "8.5/10").
- Keep it concise (2-3 sentences max). No bullet lists.

Conversation History:
{history_context}

User Query: {query}
Found Hotels (Contextual Facts — use ONLY these, no others):
{hotels_text}
"""
            
            # Escape curly braces in content to prevent .format() errors
            safe_history = history_context.replace("{", "(").replace("}", ")")
            safe_query = query.replace("{", "(").replace("}", ")")
            safe_hotels = hotels_text.replace("{", "(").replace("}", ")")
            safe_missing = missing_info.replace("{", "(").replace("}", ")")

            safe_external = external_instruction.replace("{" , "(").replace("}", ")")

            messages = [
                SystemMessage(content=system_prompt_template.format(
                    count=count,
                    external_instruction=safe_external,
                    history_context=safe_history,
                    query=safe_query, 
                    hotels_text=safe_hotels,
                    missing_info=safe_missing
                ))
            ]
            
            llm_response = self._llm_invoke_with_retry(self.llm, messages)
            response_text = llm_response.content.strip()
            
            # Fallback if LLM is being quiet
            if not response_text or len(response_text) < 5:
                count = len(hydrated_hotels)
                hotel_word = "hotel" if count == 1 else "hotels"
                response_text = f"Great! I found {count} amazing {hotel_word} that match your preferences. These are my top recommendations for you!"

            # Append external disclaimer as a trailing note
            if is_external:
                response_text += "\n\n\u26a0\ufe0f *These are external results not in our partner network. Book directly via the links provided. We cannot guarantee availability or pricing.*"

            logger.info(f"Generated UI response: {response_text[:100]}...")
            
            return {
                **state,
                "response": response_text,
                "hydrated_hotels": hydrated_hotels  # Include enriched objects
            }
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            hotels = state.get('hydrated_hotels', [])
            is_ext = state.get('is_external_search', False)
            if hotels:
                count = len(hotels)
                city_val = hotels[0].get('city', '')
                city_note = f" in {city_val}" if city_val else ""
                source_note = " (external results)" if is_ext else ""
                fallback_resp = (
                    f"I found {count} hotel{'s' if count != 1 else ''}{city_note}{source_note}. "
                    "Please check the listings below!"
                )
                if is_ext:
                    fallback_resp += (
                        "\n\n\u26a0\ufe0f *These are external results not in our partner network. "
                        "Book directly via the links provided.*"
                    )
            else:
                fallback_resp = "I couldn't find hotels matching that search right now. Please try again shortly."
            return {
                **state,
                "response": fallback_resp
            }
    
    async def run(
        self, 
        query: str, 
        history: Optional[List[Dict[str, str]]] = None, 
        shown_hotel_ids: Optional[List[int]] = None,
        last_hotels: Optional[List[Dict[str, Any]]] = None,
        skip_query_correction: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the full agent workflow.
        
        Args:
            query: User's natural language query (may already be corrected by orchestrator)
            history: Optional conversation history
            shown_hotel_ids: List of hotel IDs already shown in this session
            last_hotels: Full result set from previous search (for refinement)
            skip_query_correction: If True, skip the LLM correction call inside the agent
                (because the orchestrator already resolved the query in its classify step)
            
        Returns:
            Dictionary containing:
            - natural_language_response: Conversational response
            - recommended_hotels: List of hotel objects with all details
            - shown_hotel_ids: Updated list of shown hotel IDs for session tracking
        """
        logger.info(f"Running agent for query: {query}")
        
        # Initialize state
        initial_state = {
            "query": query,
            "history": history or [],
            "extracted_city": "",
            "search_results": [],
            "ranked_hotels": [],
            "hydrated_hotels": [],
            "response": "",
            "error": "",
            "shown_hotel_ids": shown_hotel_ids or [],
            "pagination_offset": 0,
            "filters_applied": {},
            "last_hotels": last_hotels or [],
            "is_refinement": False,
            "skip_query_correction": skip_query_correction,
            "is_external_search": False
        }
        
        try:
            # Execute the graph - need to handle async nodes
            # Note: We need to handle the hydrate node specially since it's async
            
            # Execute search and rank synchronously
            state = self._search_node(initial_state)
            
            # ── Tavily fallback: fire when DB returns nothing ─────────────
            if not state.get('search_results') and self.tavily_search and self.tavily_search.available:
                state = self._tavily_fallback_node(state)
            # ─────────────────────────────────────────────────────────────
            
            state = self._rank_node(state)
            
            # Execute hydrate asynchronously
            state = await self._hydrate_node(state)
            
            # Generate response synchronously
            final_state = self._generate_response_node(state)
            
            # Update shown hotel IDs - ensure type consistency (convert to int)
            new_hotel_ids = []
            for hotel in final_state.get("hydrated_hotels", []):
                hotel_id = hotel.get('id')
                if hotel_id:
                    try:
                        # Convert to int for consistent comparison
                        id_int = int(hotel_id) if isinstance(hotel_id, str) else hotel_id
                        new_hotel_ids.append(id_int)
                    except (ValueError, TypeError):
                        pass
            
            # Merge with existing shown IDs and deduplicate
            existing_ids = initial_state.get('shown_hotel_ids', [])
            updated_shown_ids = list(set(existing_ids + new_hotel_ids))
            
            # Strip internal-only keys before returning to the API consumer
            _internal_keys = {'_rating_imputed'}
            clean_hotels = [
                {k: v for k, v in h.items() if k not in _internal_keys}
                for h in final_state.get('hydrated_hotels', [])
            ]

            # Format output
            result = {
                "natural_language_response": final_state.get("response", ""),
                "recommended_hotels": clean_hotels,
                "last_hotels": final_state.get("search_results", []), # Pass back for multi-turn memory
                "shown_hotel_ids": updated_shown_ids,  # Return updated list for session
                "metadata": {
                    "query": query,
                    "filters_applied": final_state.get("filters_applied", {}),
                    "total_found": len(final_state.get("search_results", [])),
                    "total_shown_in_session": len(updated_shown_ids),
                    "error": final_state.get("error", "")
                }
            }
            
            logger.info(f"Agent completed successfully. Returned {len(result['recommended_hotels'])} hotels (total shown in session: {len(updated_shown_ids)})")
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return {
                "natural_language_response": f"I apologize, but I encountered an error: {str(e)}",
                "recommended_hotels": [],
                "shown_hotel_ids": shown_hotel_ids or [],
                "metadata": {
                    "query": query,
                    "error": str(e)
                }
            }
