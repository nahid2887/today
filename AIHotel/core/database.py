"""
Direct PostgreSQL Database Connection for Hotel Data.

This module provides direct database access for real-time queries,
replacing the API sync approach with direct PostgreSQL queries.
"""
import asyncpg
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """PostgreSQL connection configuration."""
    # Previous configuration
    HOST = "10.10.13.27"
    PORT = 5433
    DATABASE = "hotel_db"
    USER = "hotel_user"
    PASSWORD = "hotel_pass"

    # New configuration (10.10.13.121)
    # HOST = "10.10.13.127"
    # PORT = 5432
    # DATABASE = "hotel_db"
    # USER = "mobashir"
    # PASSWORD = "password"
    
    @classmethod
    def get_connection_string(cls) -> str:
        """Get PostgreSQL connection string."""
        return f"postgresql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}"


class HotelDatabase:
    """
    Direct PostgreSQL database access for hotel data.
    
    Provides real-time queries with filtering capabilities:
    - City filtering
    - Price range filtering
    - Rating filtering
    - Amenity filtering
    - Availability checks
    """
    
    def __init__(self):
        """Initialize database connection pool."""
        self.pool: Optional[asyncpg.Pool] = None
        self.config = DatabaseConfig()
        logger.info("HotelDatabase initialized")
    
    async def connect(self):
        """Create connection pool to PostgreSQL."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    host=self.config.HOST,
                    port=self.config.PORT,
                    database=self.config.DATABASE,
                    user=self.config.USER,
                    password=self.config.PASSWORD,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Connected to PostgreSQL database")
            except Exception as e:
                logger.error(f"❌ Failed to connect to database: {e}")
                raise
    
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Disconnected from database")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        if self.pool is None:
            await self.connect()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def get_all_hotels(
        self,
        hotel_name: Optional[str] = None,
        city: Optional[str] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        exclude_city: Optional[str] = None,
        exclude_amenities: Optional[List[str]] = None,
        exclude_ids: Optional[List[int]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query hotels with filters applied at database level.
        
        Args:
            hotel_name: Filter by name (partial match)
            city: Filter by city (case-insensitive)
            min_rating: Minimum average rating
            max_rating: Maximum average rating
            min_price: Minimum price per night
            max_price: Maximum price per night
            amenities: Required amenities (must have ALL)
            exclude_city: City to exclude
            exclude_amenities: Amenities to exclude
            exclude_ids: List of hotel IDs to exclude (e.g., already shown)
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            List of hotel dictionaries with all fields
        """
        query_parts = [
            """
            SELECT 
                id, partner_id, hotel_name, description, location, 
                city, country, amenities, images, room_type, 
                number_of_rooms, average_rating, total_ratings,
                base_price_per_night, commission_rate, updated_at as last_updated
            FROM hotel_hotel
            WHERE is_approved = 'approved'
            """
        ]
        params = []
        param_count = 1
        
        # Hotel name filter
        if hotel_name:
            query_parts.append(f"AND hotel_name ILIKE ${param_count}")
            params.append(f"%{hotel_name}%")
            param_count += 1

        # Exclude IDs filter
        if exclude_ids:
            # If we are searching for a specific name, don't exclude those IDs
            # unless they are explicitly excluded. For now, name search bypasses exclude_ids.
            if not hotel_name:
                query_parts.append(f"AND id != ALL(${param_count})")
                params.append(exclude_ids)
                param_count += 1

        # City filter (case-insensitive) - checks both city and location fields
        if city:
            query_parts.append(f"AND (LOWER(city) = LOWER(${param_count}) OR LOWER(location) LIKE LOWER(${param_count + 1}))")
            params.append(city)
            params.append(f"%{city}%")
            param_count += 2

        # Exclude city filter
        if exclude_city:
            query_parts.append(f"AND (LOWER(city) != LOWER(${param_count}) AND LOWER(location) NOT LIKE LOWER(${param_count + 1}))")
            params.append(exclude_city)
            params.append(f"%{exclude_city}%")
            param_count += 2
        
        # Rating filters
        if min_rating is not None:
            query_parts.append(f"AND average_rating >= ${param_count}")
            params.append(min_rating)
            param_count += 1
        
        if max_rating is not None:
            query_parts.append(f"AND average_rating < ${param_count}")
            params.append(max_rating)
            param_count += 1
        
        # Price filters (assuming base_price_per_night is stored as numeric/decimal)
        if min_price is not None:
            query_parts.append(f"AND base_price_per_night >= ${param_count}")
            params.append(min_price)
            param_count += 1
        
        if max_price is not None:
            query_parts.append(f"AND base_price_per_night <= ${param_count}")
            params.append(max_price)
            param_count += 1
        
        # Amenities filter (JSONB contains operator)
        if amenities:
            for amenity in amenities:
                query_parts.append(f"AND amenities @> ${param_count}::jsonb")
                import json
                params.append(json.dumps([amenity]))
                param_count += 1
        
        # Order by rating and total reviews
        query_parts.append("ORDER BY average_rating DESC, total_ratings DESC")
        
        # Pagination
        query_parts.append(f"LIMIT ${param_count} OFFSET ${param_count + 1}")
        params.extend([limit, offset])
        
        query = "\n".join(query_parts)
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *params)
                
                hotels = []
                for row in rows:
                    hotel = dict(row)
                    # Convert Decimal to float for price
                    if hotel.get('base_price_per_night'):
                        hotel['base_price_per_night'] = float(hotel['base_price_per_night'])
                    if hotel.get('commission_rate'):
                        hotel['commission_rate'] = float(hotel['commission_rate'])
                    # Convert JSONB fields to Python lists
                    import json
                    amenities_json = hotel.get('amenities', [])
                    if isinstance(amenities_json, str):
                        hotel['amenities'] = json.loads(amenities_json)
                    elif amenities_json:
                        hotel['amenities'] = amenities_json
                    else:
                        hotel['amenities'] = []
                    
                    images_json = hotel.get('images', [])
                    if isinstance(images_json, str):
                        hotel['images'] = json.loads(images_json)
                    elif images_json:
                        hotel['images'] = images_json
                    else:
                        hotel['images'] = []
                    hotels.append(hotel)
                
                logger.info(f"Found {len(hotels)} hotels with filters: city={city}, "
                          f"rating={min_rating}-{max_rating}, price={min_price}-{max_price}")
                return hotels
                
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return []
    
    async def get_hotel_by_id(self, hotel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get single hotel by ID.
        
        Args:
            hotel_id: Hotel ID
            
        Returns:
            Hotel dictionary or None if not found
        """
        query = """
            SELECT 
                id, partner_id, hotel_name, description, location, 
                city, country, amenities, images, room_type, 
                number_of_rooms, average_rating, total_ratings,
                base_price_per_night, commission_rate, updated_at as last_updated
            FROM hotel_hotel
            WHERE id = $1 AND is_approved = 'approved'
        """
        
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, hotel_id)
                
                if row:
                    hotel = dict(row)
                    if hotel.get('base_price_per_night'):
                        hotel['base_price_per_night'] = float(hotel['base_price_per_night'])
                    if hotel.get('commission_rate'):
                        hotel['commission_rate'] = float(hotel['commission_rate'])
                    hotel['amenities'] = list(hotel.get('amenities', []))
                    hotel['images'] = list(hotel.get('images', []))
                    return hotel
                
                return None
                
        except Exception as e:
            logger.error(f"Error fetching hotel {hotel_id}: {e}")
            return None
    
    async def get_cities(self) -> List[str]:
        """
        Get list of all cities with hotels.
        Extracts cities from both city and location fields.
        
        Returns:
            List of unique city names
        """
        query = """
            WITH city_list AS (
                -- Get cities from city field
                SELECT DISTINCT TRIM(city) as city_name
                FROM hotel_hotel 
                WHERE city IS NOT NULL AND city != '' AND is_approved = 'approved'
                
                UNION
                
                -- Extract city names from location field
                -- Split by comma and take first part (common format: "City, Country")
                SELECT DISTINCT TRIM(SPLIT_PART(location, ',', 1)) as city_name
                FROM hotel_hotel 
                WHERE location IS NOT NULL AND location != '' AND is_approved = 'approved'
            )
            SELECT city_name FROM city_list 
            WHERE city_name IS NOT NULL AND city_name != ''
            ORDER BY city_name
        """
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query)
                cities = [row['city_name'] for row in rows]
                logger.info(f"Found {len(cities)} cities in database")
                return cities
                
        except Exception as e:
            logger.error(f"Error fetching cities: {e}")
            return []

    async def get_amenities(self) -> List[str]:
        """
        Get list of all unique amenities available across all hotels.
        Uses PostgreSQL JSONB expansion.
        
        Returns:
            List of unique amenity tags
        """
        query = """
            SELECT DISTINCT jsonb_array_elements_text(amenities) as amenity
            FROM hotel_hotel
            WHERE amenities IS NOT NULL AND is_approved = 'approved'
            ORDER BY amenity
        """
        
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query)
                amenities = [row['amenity'] for row in rows]
                logger.info(f"Found {len(amenities)} unique amenities in database")
                return amenities
        except Exception as e:
            logger.error(f"Error fetching amenities: {e}")
            return []

    async def get_price_bounds(self) -> Dict[str, float]:
        """
        Get current min and max prices to ground the AI's understanding of "cheap" vs "expensive".
        
        Returns:
            Dictionary with 'min' and 'max' price
        """
        query = "SELECT MIN(base_price_per_night) as min, MAX(base_price_per_night) as max FROM hotel_hotel WHERE is_approved = 'approved'"
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query)
                return {
                    'min': float(row['min']) if row and row['min'] else 0.0,
                    'max': float(row['max']) if row and row['max'] else 0.0
                }
        except Exception as e:
            logger.error(f"Error fetching price bounds: {e}")
            return {'min': 0.0, 'max': 0.0}

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats (total hotels, avg rating, cities, etc.)
        """
        query = """
            SELECT 
                COUNT(*) as total_hotels,
                AVG(average_rating) as avg_rating,
                COUNT(DISTINCT city) as total_cities,
                MIN(base_price_per_night) as min_price,
                MAX(base_price_per_night) as max_price,
                AVG(base_price_per_night) as avg_price
            FROM hotel_hotel
            WHERE is_approved = 'approved'
        """
        
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query)
                
                stats = dict(row)
                if stats.get('avg_rating'):
                    stats['avg_rating'] = float(stats['avg_rating'])
                if stats.get('min_price'):
                    stats['min_price'] = float(stats['min_price'])
                if stats.get('max_price'):
                    stats['max_price'] = float(stats['max_price'])
                if stats.get('avg_price'):
                    stats['avg_price'] = float(stats['avg_price'])
                
                return stats
                
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {}
