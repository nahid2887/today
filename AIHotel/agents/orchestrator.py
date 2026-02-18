"""
Travel Assistant Orchestrator - LangGraph Router

Routes user queries to appropriate handlers:
1. Normal Chat - Greetings, small talk
2. General Travel Info - Destinations, tips, weather
3. Hotel Search - Hotel recommendations (uses HotelRecommendationAgent)

CRITICAL PROTOCOL: Agent is FORBIDDEN from external APIs.
Only the CLOSED DATABASE is used for hotel searches.
"""
import logging
from typing import Dict, Any, List, TypedDict, Literal, Optional
from enum import Enum

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from agents.hotel_agent import HotelRecommendationAgent
from core.integrated_search import IntegratedHotelSearch
from config import OPENAI_API_KEY, OPENAI_MODEL, GROQ_API_KEY, GROQ_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of queries the system can handle."""
    NORMAL_CHAT = "normal_chat"
    TRAVEL_INFO = "travel_info"
    HOTEL_SEARCH = "hotel_search"


class OrchestratorState(TypedDict):
    """
    State for the orchestrator workflow.
    """
    query: str
    history: List[Dict[str, str]]
    shown_hotel_ids: List[int]
    query_type: str
    corrected_query: str          # Resolved/corrected query from classify step
    response: str
    hotels: List[Dict[str, Any]]
    last_hotels: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    error: str


class TravelOrchestrator:
    """
    Main orchestrator for the travel assistant.
    
    Routes queries using LLM-based classification:
    - Normal Chat: Direct LLM response
    - Travel Info: LLM with travel context
    - Hotel Search: HotelRecommendationAgent
    """
    
    def __init__(self, search_system: IntegratedHotelSearch):
        """
        Initialize the orchestrator.
        
        Args:
            search_system: Instance of IntegratedHotelSearch for hotel queries
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
            #     logger.info(f"Orchestrator using OpenAI model: {OPENAI_MODEL}")
            # elif GROQ_API_KEY:
            if GROQ_API_KEY:
                self.llm = ChatGroq(
                    groq_api_key=GROQ_API_KEY,
                    model_name=GROQ_MODEL,
                    temperature=0.3,
                    max_tokens=1024
                )
                # Cheap LLM for classify + query correction (returns 2 lines)
                self.llm_classifier = ChatGroq(
                    groq_api_key=GROQ_API_KEY,
                    model_name=GROQ_MODEL,
                    temperature=0.0,
                    max_tokens=80
                )
                logger.info(f"Orchestrator using Groq model: {GROQ_MODEL}")
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
            # else:
            #     raise
            raise
        
        # Initialize hotel search agent
        self.hotel_agent = HotelRecommendationAgent(search_system)
        
        # Build the orchestration graph
        self.graph = self._build_graph()
        
        logger.info("TravelOrchestrator initialized with routing capability")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph orchestration workflow.
        
        Flow:
        1. Classify query → Determine query type
        2. Route based on type:
           - normal_chat → handle_normal_chat
           - travel_info → handle_travel_info
           - hotel_search → handle_hotel_search
        3. END
        """
        workflow = StateGraph(OrchestratorState)
        
        # Add nodes
        workflow.add_node("classify", self._classify_query)
        workflow.add_node("normal_chat", self._handle_normal_chat)
        workflow.add_node("travel_info", self._handle_travel_info)
        workflow.add_node("hotel_search", self._handle_hotel_search)
        
        # Set entry point
        workflow.set_entry_point("classify")
        
        # Add conditional routing from classify
        workflow.add_conditional_edges(
            "classify",
            self._route_query,
            {
                QueryType.NORMAL_CHAT: "normal_chat",
                QueryType.TRAVEL_INFO: "travel_info",
                QueryType.HOTEL_SEARCH: "hotel_search",
            }
        )
        
        # All handlers lead to END
        workflow.add_edge("normal_chat", END)
        workflow.add_edge("travel_info", END)
        workflow.add_edge("hotel_search", END)
        
        return workflow.compile()
    
    async def _classify_query(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Classify the user query AND resolve query context in one LLM call.

        For hotel searches, also returns a corrected/resolved query so the
        hotel agent can skip its own second LLM correction call.
        """
        query = state['query']
        query_lower = query.lower().strip()

        logger.info(f"[CLASSIFY] Analyzing query: {query}")

        import re
        # Fast pattern-match FIRST — skip DB call + LLM entirely for greetings
        conversational_patterns = [
            r'\bhello\b', r'\bhi\b', r'\bhey\b', r'\bgreetings\b', r'\bgood morning\b',
            r'\bgood afternoon\b', r'\bgood evening\b', r'\bgood night\b', r'\bhowdy\b',
            r'\bthanks\b', r'\bthank you\b', r'\bcheers\b', r'\bthx\b',
            r'\bbye\b', r'\bgoodbye\b', r'\bhow are you\b', r'\bwhats up\b',
            r'\bok\b', r'\bokay\b', r'\bgot it\b'
        ]
        if any(re.search(pattern, query_lower) for pattern in conversational_patterns):
            logger.info("[CLASSIFY] Pattern matched: NORMAL_CHAT")
            return {**state, "query_type": QueryType.NORMAL_CHAT.value}

        # Get available cities (cached — no DB hit after first connect)
        available_cities = await self.search_system.get_available_cities()
        cities_str = ", ".join(available_cities) if available_cities else "None"

        # Short query with a known city → definitely hotel search, skip LLM
        if len(query_lower.split()) <= 3:
            for city in available_cities:
                if city.lower() in query_lower:
                    logger.info(f"[CLASSIFY] City mention in short query: {city} → HOTEL_SEARCH")
                    return {**state, "query_type": QueryType.HOTEL_SEARCH.value,
                            "corrected_query": query}

        # Format recent history
        history_context = ""
        if state.get('history'):
            for msg in state['history'][-4:]:
                role = "User" if msg['role'] == 'user' else "Assistant"
                history_context += f"{role}: {msg['content']}\n"

        try:
            # ONE combined prompt: classify + correct the query in a single call
            combined_prompt = f"""You are a travel assistant classifier and query resolver.

Cities in our database: {cities_str}

Task 1 - CLASSIFY the user query as one of:
  NORMAL_CHAT  - greetings, thanks, bye, casual talk
  TRAVEL_INFO  - general travel questions, destinations, tips (NOT hotel search)
  HOTEL_SEARCH - finding/recommending hotels, room search, accommodation

Task 2 - If HOTEL_SEARCH, produce a CORRECTED QUERY following these rules:
  - Fix city name typos ("cumilla" -> "Comilla", "sydny" -> "Sydney")
  - If the user does NOT mention a city, CARRY OVER the last city from conversation
    history. Users typically stay in the same city across a session.
    Examples (last city was Melbourne):
      "best rated hotels"       → QUERY: best rated hotels in Melbourne
      "hotels with pool"        → QUERY: hotels with pool in Melbourne
      "cheap ones under $100"   → QUERY: cheap hotels under $100 in Melbourne
  - Only DROP the carried-over city if the user clearly mentions a DIFFERENT city
    or asks something city-agnostic like "any country" / "worldwide".
  - If there is NO city in history at all, output the query as-is with no city added.
  - Preserve budget/amenity constraints if query is a follow-up refinement.
  - Output ONLY the search query, no explanation.

Conversation History:
{history_context}

User Query: "{query}"

Respond in EXACTLY this format (two lines):
TYPE: <NORMAL_CHAT|TRAVEL_INFO|HOTEL_SEARCH>
QUERY: <corrected search query, or NONE if not hotel search>"""

            response = self.llm_classifier.invoke([HumanMessage(content=combined_prompt)])
            raw = response.content.strip()

            # Parse the two-line response
            query_type = QueryType.HOTEL_SEARCH  # default
            corrected_query = query
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("TYPE:"):
                    tipo = line.split("TYPE:", 1)[1].strip().upper()
                    if "NORMAL_CHAT" in tipo:
                        query_type = QueryType.NORMAL_CHAT
                    elif "TRAVEL_INFO" in tipo:
                        query_type = QueryType.TRAVEL_INFO
                    else:
                        query_type = QueryType.HOTEL_SEARCH
                elif line.startswith("QUERY:"):
                    q = line.split("QUERY:", 1)[1].strip().strip('"').strip("'")
                    if q and q.upper() != "NONE":
                        corrected_query = q

            logger.info(f"[CLASSIFY] Query type: {query_type}, corrected: '{corrected_query}'")
            return {
                **state,
                "query_type": query_type.value,
                "corrected_query": corrected_query
            }

        except Exception as e:
            logger.error(f"Classification error: {e}")
            # Fallback
            convos = ['hello', 'hi', 'hey', 'thanks', 'thank you', 'bye', 'goodbye',
                      'good morning', 'good afternoon', 'good evening', 'how are you']
            if any(p in query_lower for p in convos):
                return {**state, "query_type": QueryType.NORMAL_CHAT.value}
            return {**state, "query_type": QueryType.HOTEL_SEARCH.value}
    
    def _route_query(self, state: OrchestratorState) -> str:
        """
        Route based on classified query type.
        
        Returns:
            Node name to route to
        """
        query_type = state.get('query_type', QueryType.HOTEL_SEARCH.value)
        logger.info(f"[ROUTE] Routing to: {query_type}")
        return query_type
    
    def _handle_normal_chat(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Handle normal chat/greetings with direct LLM response.
        """
        logger.info("[NORMAL_CHAT] Handling casual conversation")
        
        query = state['query']
        history = state.get('history', [])
        
        try:
            # Build context from history
            history_context = ""
            if history:
                recent_history = history[-4:]  # Last 2 exchanges
                for msg in recent_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    history_context += f"{role.title()}: {content}\n"
            
            system_prompt = """You are a friendly travel assistant. 
Respond naturally to greetings and casual conversation.
Keep responses brief and warm. Always be ready to help with travel or hotel queries."""
            
            user_prompt = f"""Previous conversation:
{history_context}

Current message: {query}

Respond naturally and offer to help with travel planning or hotel search."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            logger.info(f"[NORMAL_CHAT] Response: {response_text[:100]}...")
            
            return {
                **state,
                "response": response_text,
                "hotels": [],
                "metadata": {
                    "query_type": "normal_chat",
                    "query": query
                }
            }
            
        except Exception as e:
            logger.error(f"Normal chat error: {e}")
            return {
                **state,
                "response": "Hello! How can I help you with your travel plans today?",
                "hotels": [],
                "metadata": {"error": str(e)}
            }
    
    def _handle_travel_info(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Handle general travel information queries.
        
        IMPORTANT: Uses LLM knowledge, NOT external APIs.
        Stays within the CLOSED system boundary.
        """
        logger.info("[TRAVEL_INFO] Handling general travel query")
        
        query = state['query']
        history = state.get('history', [])
        
        try:
            # Build context from history
            history_context = ""
            if history:
                recent_history = history[-4:]
                for msg in recent_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    history_context += f"{role.title()}: {content}\n"
            
            system_prompt = """You are a knowledgeable travel assistant.
Provide helpful information about destinations, travel tips, activities, and culture.
Use your training knowledge - do NOT mention accessing external APIs or real-time data.

IMPORTANT: 
- Base answers on your training knowledge
- For hotel recommendations, suggest the user ask about "hotels in [destination]"
- Keep responses informative but concise (3-4 sentences)
- Always end by offering to help find hotels if they need accommodation"""
            
            user_prompt = f"""Previous conversation:
{history_context}

Travel Question: {query}

Provide helpful travel information and offer to help find hotels if needed."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            logger.info(f"[TRAVEL_INFO] Response: {response_text[:100]}...")
            
            return {
                **state,
                "response": response_text,
                "hotels": [],
                "metadata": {
                    "query_type": "travel_info",
                    "query": query
                }
            }
            
        except Exception as e:
            logger.error(f"Travel info error: {e}")
            return {
                **state,
                "response": "I'd be happy to help with travel information! Could you tell me more about what you'd like to know?",
                "hotels": [],
                "metadata": {"error": str(e)}
            }
    
    async def _handle_hotel_search(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Handle hotel search queries using HotelRecommendationAgent.
        Uses pre-resolved corrected_query from the classify step to avoid
        a second LLM call inside the hotel agent.
        """
        logger.info("[HOTEL_SEARCH] Routing to HotelRecommendationAgent")

        # Use the corrected query produced by classify if available
        query = state.get('corrected_query') or state['query']
        history = state.get('history', [])
        shown_hotel_ids = state.get('shown_hotel_ids', [])
        last_hotels = state.get('last_hotels', [])
        
        try:
            # Pass the already-corrected query; hotel agent will skip its own correction call
            result = await self.hotel_agent.run(
                query=query,
                history=history,
                shown_hotel_ids=shown_hotel_ids,
                last_hotels=last_hotels,
                skip_query_correction=True  # classify already did this
            )
            
            logger.info(f"[HOTEL_SEARCH] Found {len(result['recommended_hotels'])} hotels")
            
            return {
                **state,
                "response": result['natural_language_response'],
                "hotels": result['recommended_hotels'],
                "last_hotels": result.get('last_hotels', []),
                "shown_hotel_ids": result['shown_hotel_ids'],
                "metadata": result.get('metadata', {})
            }
            
        except Exception as e:
            logger.error(f"Hotel search error: {e}")
            return {
                **state,
                "response": "I encountered an issue searching for hotels. Please try again.",
                "hotels": [],
                "metadata": {"error": str(e)}
            }
    
    async def run(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        shown_hotel_ids: Optional[List[int]] = None,
        last_hotels: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Execute the orchestration workflow.
        
        Args:
            query: User's query
            history: Conversation history
            shown_hotel_ids: Hotels already shown in this session
            last_hotels: Hotels from the previous turn
            
        Returns:
            Dictionary with response, hotels, and metadata
        """
        logger.info(f"[ORCHESTRATOR] Processing query: {query}")
        
        # Initialize state
        initial_state = {
            "query": query,
            "history": history or [],
            "shown_hotel_ids": shown_hotel_ids or [],
            "last_hotels": last_hotels or [],
            "query_type": "",
            "response": "",
            "hotels": [],
            "metadata": {},
            "error": ""
        }
        
        try:
            # Execute workflow
            # Need to handle async hotel search node
            state = await self._classify_query(initial_state)
            
            query_type = state.get('query_type', '')
            
            if query_type == QueryType.NORMAL_CHAT.value:
                final_state = self._handle_normal_chat(state)
            elif query_type == QueryType.TRAVEL_INFO.value:
                final_state = self._handle_travel_info(state)
            else:  # HOTEL_SEARCH
                final_state = await self._handle_hotel_search(state)
            
            logger.info(f"[ORCHESTRATOR] Completed with type: {query_type}")
            
            return {
                "natural_language_response": final_state.get("response", ""),
                "recommended_hotels": final_state.get("hotels", []),
                "last_hotels": final_state.get("last_hotels", []),
                "shown_hotel_ids": final_state.get("shown_hotel_ids") or shown_hotel_ids or [],
                "metadata": {
                    **final_state.get("metadata", {}),
                    "query_type": query_type,
                    "query": query
                }
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return {
                "natural_language_response": f"I encountered an error: {str(e)}",
                "recommended_hotels": [],
                "shown_hotel_ids": shown_hotel_ids or [],
                "metadata": {
                    "query": query,
                    "error": str(e)
                }
            }
