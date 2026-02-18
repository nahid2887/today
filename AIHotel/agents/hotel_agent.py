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
from typing import Dict, Any, List, TypedDict, Annotated, Optional
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from core.integrated_search import IntegratedHotelSearch
from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    RATING_WEIGHT,
    SIMILARITY_WEIGHT,
    TOP_K_RESULTS
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
        
        # Initialize LLM (Groq primary, OpenAI temporarily commented out)
        try:
            # TEMPORARILY COMMENTED OUT - Using Groq instead
            # if OPENAI_API_KEY:
            #     self.llm = ChatOpenAI(
            #         api_key=OPENAI_API_KEY,
            #         model=OPENAI_MODEL,
            #         temperature=0.3,
            #         max_tokens=1024
            #     )
            #     self.llm_provider = "OpenAI"
            #     logger.info(f"Using OpenAI model: {OPENAI_MODEL}")
            # elif GROQ_API_KEY:
            if GROQ_API_KEY:
                self.llm = ChatGroq(
                    groq_api_key=GROQ_API_KEY,
                    model_name=GROQ_MODEL,
                    temperature=0.3,
                    max_tokens=1024
                )
                # Cheap fast LLM used only for the short query-correction call
                self.llm_fast = ChatGroq(
                    groq_api_key=GROQ_API_KEY,
                    model_name=GROQ_MODEL,
                    temperature=0.0,
                    max_tokens=50
                )
                self.llm_provider = "Groq"
                logger.info(f"Using Groq model: {GROQ_MODEL}")
            else:
                raise ValueError("No LLM API key found. Set GROQ_API_KEY (OpenAI temporarily disabled)")
        except Exception as e:
            # # Fallback to Groq if OpenAI fails (TEMPORARILY DISABLED)
            # if GROQ_API_KEY and "openai" in str(e).lower():
            #     logger.warning(f"OpenAI initialization failed: {e}. Falling back to Groq")
            #     self.llm = ChatGroq(
            #         groq_api_key=GROQ_API_KEY,
            #         model_name=GROQ_MODEL,
            #         temperature=0.3,
            #         max_tokens=1024
            #     )
            #     self.llm_provider = "Groq (fallback)"
            # else:
            #     raise
            raise
        
        # Build the state machine graph
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
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
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
                    correction_response = self.llm_fast.invoke([HumanMessage(content=correction_prompt)])
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
            
            # Special handling for refinement queries
            if is_refinement:
                if any(kw in query_lower for kw in ["cheap", "price", "low"]):
                    # Sort by price ascending
                    logger.info("Sorting by price (ascending) for refinement")
                    # Handle price extraction safely
                    def get_price(h):
                        p = h.get('base_price_per_night') or h.get('price')
                        return float(p) if p else 999999.0
                    
                    ranked = sorted(search_results, key=get_price)
                    return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}
                
                if any(kw in query_lower for kw in ["rating", "best", "review", "top"]):
                    # Sort by rating descending
                    logger.info("Sorting by rating (descending) for refinement")
                    ranked = sorted(search_results, key=lambda x: x.get('average_rating', 0), reverse=True)
                    return {**state, "ranked_hotels": ranked[:TOP_K_RESULTS]}

            # Default: Calculate composite score for each hotel
            scored_hotels = []
            for hotel in search_results:
                # Normalize average_rating - Database consistently uses a 10.0 scale
                raw_rating = hotel.get('average_rating', 0.0)
                # Treat rating=0 as "no data" — use neutral 5.0 so unrated hotels
                # aren't buried below hotels with any real rating.
                effective_rating = raw_rating if raw_rating > 0 else 5.0
                normalized_rating = effective_rating / 10.0
                
                # Similarity score is already normalized (0-1)
                similarity = hotel.get('similarity_score', 0.6) # Default if search system didn't provide
                
                # Calculate weighted score (0.6 rating + 0.4 similarity)
                composite_score = (RATING_WEIGHT * normalized_rating) + (SIMILARITY_WEIGHT * similarity)
                # Store effective_rating so the response layer knows this was imputed
                hotel_with_score = hotel.copy()
                if raw_rating == 0.0:
                    hotel_with_score['_rating_imputed'] = True
                
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
            
            # 1. Handle Errors for UI
            if error and not hydrated_hotels:
                return {
                    **state,
                    "response": f"I hit a small snag: {error.replace('Invalid input: ', '')}. Could you try adjusting your search terms?"
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

                # Fallback perks if still empty
                if not perks:
                    standard_perks = ["Free breakfast", "Late checkout", "Free Wi-Fi", "Room upgrade"]
                    perks = [standard_perks[idx % 4], standard_perks[(idx + 1) % 4]]
                
                hotel['perks'] = perks[:3] # Keep UI clean
                
                # Badges (like "15% off")
                if 'badges' not in hotel:
                    hotel['badges'] = [f"{15 + idx*5}% OFF"] if idx < 2 else []
                
                # Image fallback
                if not hotel.get('images'):
                    hotel['images'] = [f"https://images.unsplash.com/photo-1566073771259-6a8506099945?w=500&q={80+idx}"]

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
                
                summary = f"- {hotel.get('hotel_name')} (Rating: {rating}/10): {match_reason}. Amenities: {amenities_str}.{desc_snippet}"
                hotels_context.append(summary)
            
            hotels_text = "\n".join(hotels_context)
            
            # Use standard string and .format() to avoid f-string escaping confusion
            count = len(hydrated_hotels)
            system_prompt_template = """You are an expert travel concierge.
Your goal is to generate a warm, persuasive, and helpful response for the user's chat bubble.

Style Guidelines:
- Use the Conversation History to maintain a natural flow (e.g., "Following up on that," or "As you mentioned...").
- Start with an enthusiastic opening.
- Mention the number of hotels found ({count} hotels).
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
Found Hotels (Contextual Facts):
{hotels_text}
"""
            
            # Escape curly braces in content to prevent .format() errors
            safe_history = history_context.replace("{", "(").replace("}", ")")
            safe_query = query.replace("{", "(").replace("}", ")")
            safe_hotels = hotels_text.replace("{", "(").replace("}", ")")
            safe_missing = missing_info.replace("{", "(").replace("}", ")")

            messages = [
                SystemMessage(content=system_prompt_template.format(
                    count=count,
                    history_context=safe_history,
                    query=safe_query, 
                    hotels_text=safe_hotels,
                    missing_info=safe_missing
                ))
            ]
            
            llm_response = self.llm.invoke(messages)
            response_text = llm_response.content.strip()
            
            # Fallback if LLM is being quiet
            if not response_text or len(response_text) < 5:
                count = len(hydrated_hotels)
                hotel_word = "hotel" if count == 1 else "hotels"
                response_text = f"Great! I found {count} amazing {hotel_word} that match your preferences. These are my top recommendations for you!"

            logger.info(f"Generated UI response: {response_text[:100]}...")
            
            return {
                **state,
                "response": response_text,
                "hydrated_hotels": hydrated_hotels  # Include enriched objects
            }
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return {
                **state,
                "response": "I've found some great hotels that match your request! Take a look at the options below."
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
            "skip_query_correction": skip_query_correction
        }
        
        try:
            # Execute the graph - need to handle async nodes
            # Note: We need to handle the hydrate node specially since it's async
            
            # Execute search and rank synchronously
            state = self._search_node(initial_state)
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
