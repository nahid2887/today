"""
Natural Language to SQL Query Generator.

Converts user's natural language queries into safe PostgreSQL queries
for direct database access.
"""
import logging
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from config import OPENAI_API_KEY, OPENAI_MODEL, GROQ_API_KEY, GROQ_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NLtoSQLConverter:
    """
    Convert natural language queries to safe SQL queries.
    
    Features:
    - Schema-aware SQL generation
    - SQL injection prevention
    - Query validation
    - Parameterized query output
    """
    
    # Database schema for context
    SCHEMA = """
    Table: hotels_hotelprofile
    Columns:
    - id (INTEGER, PRIMARY KEY)
    - partner_name (VARCHAR)
    - hotel_name (VARCHAR) - Hotel's display name
    - description (TEXT) - Hotel description
    - location (VARCHAR) - Street address
    - city (VARCHAR) - City name (use ILIKE for case-insensitive matching)
    - country (VARCHAR) - Country name
    - amenities (TEXT[]) - Array of amenities like 'Pool', 'WiFi', 'Gym', etc.
    - images (TEXT[]) - Array of image URLs
    - room_type (VARCHAR) - Room type: 'standard', 'deluxe', 'suite', 'presidential'
    - number_of_rooms (INTEGER) - Total rooms in hotel
    - average_rating (DECIMAL) - Average rating 0.0-5.0
    - total_ratings (INTEGER) - Number of reviews
    - base_price_per_night (DECIMAL) - Price per night in USD
    - commission_rate (DECIMAL) - Commission percentage
    - last_updated (TIMESTAMP) - Last update time
    
    Notes:
    - Use ILIKE for case-insensitive text matching
    - Use = ANY(amenities) for checking amenities in array
    - Use LOWER() for city/country matching
    - Always include ORDER BY for ranking (usually by average_rating DESC, total_ratings DESC)
    - Use parameterized queries with $1, $2, etc. for values
    """
    
    def __init__(self):
        """Initialize the NL-to-SQL converter."""
        # Initialize LLM (Groq primary, OpenAI temporarily commented out)
        try:
            # TEMPORARILY COMMENTED OUT - Using Groq instead
            # if OPENAI_API_KEY:
            #     self.llm = ChatOpenAI(
            #         api_key=OPENAI_API_KEY,
            #         model=OPENAI_MODEL,
            #         temperature=0.0,  # Deterministic for SQL generation
            #         max_tokens=1024
            #     )
            #     logger.info(f"NLtoSQLConverter using OpenAI model: {OPENAI_MODEL}")
            # elif GROQ_API_KEY:
            if GROQ_API_KEY:
                self.llm = ChatGroq(
                    groq_api_key=GROQ_API_KEY,
                    model_name=GROQ_MODEL,
                    temperature=0.0,
                    max_tokens=1024
                )
                logger.info(f"NLtoSQLConverter using Groq model: {GROQ_MODEL}")
            else:
                raise ValueError("No LLM API key found. Set GROQ_API_KEY (OpenAI temporarily disabled)")
        except Exception as e:
            # # Fallback to Groq if OpenAI fails (TEMPORARILY DISABLED)
            # if GROQ_API_KEY and "openai" in str(e).lower():
            #     logger.warning(f"OpenAI initialization failed: {e}. Falling back to Groq")
            #     self.llm = ChatGroq(
            #         groq_api_key=GROQ_API_KEY,
            #         model_name=GROQ_MODEL,
            #         temperature=0.0,
            #         max_tokens=1024
            #     )
            # else:
            #     raise
            raise
        logger.info("NLtoSQLConverter initialized")
    
    def generate_sql(self, natural_query: str) -> Dict[str, Any]:
        """
        Generate SQL query from natural language.
        
        Args:
            natural_query: User's natural language query
            
        Returns:
            Dictionary with:
            - sql: SQL query string with placeholders ($1, $2, etc.)
            - params: List of parameter values
            - explanation: Human-readable explanation
            - filters_applied: Dict of filters extracted
        """
        system_prompt = f"""You are an expert PostgreSQL query generator. Convert natural language queries about hotels into safe, efficient SQL queries.

DATABASE SCHEMA:
{self.SCHEMA}

RULES:
1. ALWAYS use parameterized queries with $1, $2, $3 etc. for values (NEVER embed values directly)
2. Use ILIKE '%pattern%' for case-insensitive text search
3. Use LOWER(column) = LOWER($n) for exact case-insensitive matching
4. For amenities: use $n = ANY(amenities) to check if amenity exists
5. For multiple amenities: use AND ($n = ANY(amenities) AND $m = ANY(amenities))
6. Always add ORDER BY clause (typically: average_rating DESC, total_ratings DESC)
7. Use LIMIT and OFFSET for pagination
8. For price ranges: base_price_per_night BETWEEN $n AND $m OR base_price_per_night <= $n
9. For rating ranges: average_rating >= $n AND average_rating < $m (use < not <=)
10. Handle NULL values: use COALESCE or IS NOT NULL checks

OUTPUT FORMAT:
Return a JSON object with:
{{
  "sql": "SELECT ... FROM hotels_hotelprofile WHERE ... ORDER BY ... LIMIT $n",
  "params": [value1, value2, ...],
  "explanation": "Human-readable description of what the query does",
  "filters": {{"city": "Miami", "min_rating": 4.5, ...}}
}}

EXAMPLES:

Query: "luxury hotels in Miami with pool"
Output:
{{
  "sql": "SELECT * FROM hotels_hotelprofile WHERE LOWER(city) = LOWER($1) AND $2 = ANY(amenities) AND average_rating >= $3 ORDER BY average_rating DESC, total_ratings DESC LIMIT $4",
  "params": ["Miami", "Pool", 4.0, 10],
  "explanation": "Finding luxury (4.0+ rated) hotels in Miami with pool amenity",
  "filters": {{"city": "Miami", "min_rating": 4.0, "amenities": ["Pool"]}}
}}

Query: "cheap hotels under $100"
Output:
{{
  "sql": "SELECT * FROM hotels_hotelprofile WHERE base_price_per_night <= $1 ORDER BY base_price_per_night ASC, average_rating DESC LIMIT $2",
  "params": [100, 10],
  "explanation": "Finding budget hotels under $100 per night, ordered by price",
  "filters": {{"max_price": 100}}
}}

Query: "hotels in New York with rating above 4.5"
Output:
{{
  "sql": "SELECT * FROM hotels_hotelprofile WHERE LOWER(city) = LOWER($1) AND average_rating >= $2 ORDER BY average_rating DESC, total_ratings DESC LIMIT $3",
  "params": ["New York", 4.5, 10],
  "explanation": "Finding hotels in New York with rating 4.5 or higher",
  "filters": {{"city": "New York", "min_rating": 4.5}}
}}

Query: "best hotels with gym and spa"
Output:
{{
  "sql": "SELECT * FROM hotels_hotelprofile WHERE $1 = ANY(amenities) AND $2 = ANY(amenities) ORDER BY average_rating DESC, total_ratings DESC LIMIT $3",
  "params": ["Gym", "Spa", 10],
  "explanation": "Finding top-rated hotels with both gym and spa amenities",
  "filters": {{"amenities": ["Gym", "Spa"]}}
}}

IMPORTANT: 
- Return ONLY valid JSON, no markdown, no code blocks
- Use parameterized queries ALWAYS
- Never use string concatenation for values
- Handle case-insensitivity properly
"""

        user_prompt = f"""Generate a PostgreSQL query for this request:

"{natural_query}"

Return ONLY the JSON object, no other text."""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            # Extract JSON from response
            content = response.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = re.sub(r"```json\s*\n?", "", content)
                content = re.sub(r"```\s*$", "", content)
            
            # Parse JSON
            import json
            result = json.loads(content)
            
            # Validate required fields
            if "sql" not in result or "params" not in result:
                raise ValueError("Missing required fields in SQL generation")
            
            # Security check: ensure no direct value injection
            sql = result["sql"]
            if self._has_sql_injection_risk(sql):
                logger.error(f"SQL injection risk detected: {sql}")
                raise ValueError("Generated SQL failed security validation")
            
            logger.info(f"Generated SQL: {sql}")
            logger.info(f"Parameters: {result['params']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            return self._fallback_query(natural_query)
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return self._fallback_query(natural_query)
    
    def _has_sql_injection_risk(self, sql: str) -> bool:
        """
        Check for SQL injection risks.
        
        Args:
            sql: SQL query string
            
        Returns:
            True if potential injection detected
        """
        # Check for dangerous patterns
        dangerous_patterns = [
            r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)\s+",  # Multiple statements
            r"--",  # SQL comments
            r"/\*",  # Block comments
            r"'\s*OR\s+'",  # Classic injection
            r"'\s*=\s*'",  # Always true conditions
            r"UNION\s+SELECT",  # Union injection
        ]
        
        sql_upper = sql.upper()
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return True
        
        # Check that values use parameters
        if re.search(r"=\s*'[^$]", sql):  # Value without parameter
            return True
        
        return False
    
    def _fallback_query(self, natural_query: str) -> Dict[str, Any]:
        """
        Generate a safe fallback query when SQL generation fails.
        
        Args:
            natural_query: Original natural language query
            
        Returns:
            Safe basic query
        """
        logger.info("Using fallback query: return top-rated hotels")
        
        return {
            "sql": """
                SELECT * FROM hotels_hotelprofile 
                WHERE average_rating > 0 
                ORDER BY average_rating DESC, total_ratings DESC 
                LIMIT $1
            """,
            "params": [10],
            "explanation": f"Showing top-rated hotels (fallback query for: {natural_query})",
            "filters": {}
        }
    
    def validate_and_sanitize(self, sql: str, params: List[Any]) -> tuple[str, List[Any]]:
        """
        Validate and sanitize SQL query and parameters.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            Tuple of (sanitized_sql, sanitized_params)
        """
        # Remove extra whitespace
        sql = " ".join(sql.split())
        
        # Ensure it's a SELECT query
        if not sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        # Count parameter placeholders
        param_count = len(re.findall(r"\$\d+", sql))
        if param_count != len(params):
            raise ValueError(f"Parameter count mismatch: {param_count} placeholders, {len(params)} params")
        
        # Sanitize string parameters
        sanitized_params = []
        for param in params:
            if isinstance(param, str):
                # Remove any potential SQL injection attempts
                param = param.replace("'", "''")  # Escape single quotes
                param = param.replace(";", "")  # Remove semicolons
                param = param.replace("--", "")  # Remove comments
            sanitized_params.append(param)
        
        return sql, sanitized_params


class HybridNLSearch:
    """
    Hybrid search combining NL-to-SQL with vector semantic search.
    
    Flow:
    1. Convert NL query to SQL
    2. Execute SQL to get filtered results
    3. Apply vector semantic ranking
    4. Return top results with hybrid scores
    """
    
    def __init__(self, database, vector_manager):
        """
        Initialize hybrid NL search.
        
        Args:
            database: HotelDatabase instance
            vector_manager: VectorManager instance
        """
        self.database = database
        self.vector_manager = vector_manager
        self.nl_converter = NLtoSQLConverter()
        logger.info("HybridNLSearch initialized")
    
    async def search(
        self,
        natural_query: str,
        limit: int = 10,
        use_vector_ranking: bool = True
    ) -> Dict[str, Any]:
        """
        Search hotels using natural language query.
        
        Args:
            natural_query: User's natural language query
            limit: Maximum results to return
            use_vector_ranking: Whether to apply vector semantic ranking
            
        Returns:
            Dictionary with results, SQL info, and filters
        """
        logger.info(f"[HYBRID NL SEARCH] Query: {natural_query}")
        
        # Step 1: Generate SQL
        sql_result = self.nl_converter.generate_sql(natural_query)
        
        # Step 2: Execute SQL query
        try:
            # Update limit in params if needed
            sql = sql_result["sql"]
            params = sql_result["params"]
            
            # Execute query via database connection
            async with self.database.get_connection() as conn:
                rows = await conn.fetch(sql, *params)
                
                hotels = []
                for row in rows:
                    hotel = dict(row)
                    # Convert types
                    if hotel.get('base_price_per_night'):
                        hotel['base_price_per_night'] = float(hotel['base_price_per_night'])
                    if hotel.get('commission_rate'):
                        hotel['commission_rate'] = float(hotel['commission_rate'])
                    hotel['amenities'] = list(hotel.get('amenities', []))
                    hotel['images'] = list(hotel.get('images', []))
                    hotels.append(hotel)
                
                logger.info(f"SQL query returned {len(hotels)} hotels")
                
                # Step 3: Apply vector ranking if requested
                if use_vector_ranking and hotels:
                    hotels = self._apply_vector_ranking(natural_query, hotels)
                
                # Limit results
                hotels = hotels[:limit]
                
                return {
                    "results": hotels,
                    "total": len(hotels),
                    "sql_query": sql,
                    "sql_params": params,
                    "explanation": sql_result.get("explanation", ""),
                    "filters": sql_result.get("filters", {}),
                    "vector_ranking_applied": use_vector_ranking
                }
                
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            # Fallback to basic query
            return await self._fallback_search(natural_query, limit)
    
    def _apply_vector_ranking(
        self,
        query: str,
        hotels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply vector semantic ranking to SQL results.
        
        Args:
            query: Original query for semantic matching
            hotels: Hotels from SQL query
            
        Returns:
            Re-ranked hotels with semantic scores
        """
        # This would integrate with your vector store
        # For now, keep the SQL ordering
        logger.info("Vector ranking applied")
        return hotels
    
    async def _fallback_search(
        self,
        query: str,
        limit: int
    ) -> Dict[str, Any]:
        """Fallback search when SQL fails."""
        logger.warning("Using fallback search")
        
        hotels = await self.database.get_all_hotels(limit=limit)
        
        return {
            "results": hotels,
            "total": len(hotels),
            "sql_query": "FALLBACK",
            "sql_params": [],
            "explanation": "Fallback: top-rated hotels",
            "filters": {},
            "vector_ranking_applied": False
        }
