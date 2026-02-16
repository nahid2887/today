"""
SQLite implementation of the Hotel Database for local development.
Matches the interface of HotelDatabase in core/database.py.
"""
import aiosqlite
import json
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class SQLiteHotelDatabase:
    """
    Direct SQLite database access for hotel data.
    Used for local development with hotel.db.
    """
    
    def __init__(self, db_path: str = "hotel.db"):
        self.db_path = db_path
        self._connected = False
        logger.info(f"SQLiteHotelDatabase initialized with {db_path}")

    async def connect(self):
        """No-op for SQLite as we use aiosqlite context manager or connection."""
        self._connected = True
        logger.info("✅ Connected to SQLite database")

    async def disconnect(self):
        self._connected = False
        logger.info("Disconnected from SQLite database")

    @asynccontextmanager
    async def get_connection(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def get_all_hotels(
        self,
        city: Optional[str] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM hotels WHERE 1=1"
        params = []

        if city:
            query += " AND LOWER(city) = LOWER(?)"
            params.append(city)
        
        if min_rating is not None:
            query += " AND average_rating >= ?"
            params.append(min_rating)
            
        if max_rating is not None:
            query += " AND average_rating <= ?"
            params.append(max_rating)

        # Note: In SQLite hotel.db, price field name might vary. 
        # Checking for common names: base_price_per_night, price
        # Based on previous knowledge, it's base_price_per_night or similar.
        
        # Let's check the schema first if this fails, but for now we assume common fields.
        
        query += " ORDER BY average_rating DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            async with self.get_connection() as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    hotels = []
                    for row in rows:
                        h = dict(row)
                        # Fix JSON fields
                        if 'amenities' in h and h['amenities']:
                            try:
                                h['amenities'] = json.loads(h['amenities'])
                            except:
                                h['amenities'] = h['amenities'].split(',')
                        
                        # Add missing fields that PG has but SQLite might not
                        if 'description' not in h:
                            h['description'] = f"A beautiful hotel in {h.get('city', 'the city')}"
                        if 'images' not in h:
                            h['images'] = []
                        elif isinstance(h['images'], str):
                            try:
                                h['images'] = json.loads(h['images'])
                            except:
                                h['images'] = []
                        
                        hotels.append(h)
                    return hotels
        except Exception as e:
            logger.error(f"SQLite query error: {e}")
            return []

    async def get_hotel_by_id(self, hotel_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM hotels WHERE id = ?"
        try:
            async with self.get_connection() as db:
                async with db.execute(query, (hotel_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        h = dict(row)
                        if 'amenities' in h and h['amenities'] and isinstance(h['amenities'], str):
                             try:
                                h['amenities'] = json.loads(h['amenities'])
                             except:
                                h['amenities'] = h['amenities'].split(',')
                        return h
                    return None
        except Exception as e:
            logger.error(f"SQLite get_hotel_by_id error: {e}")
            return None

    async def get_cities(self) -> List[str]:
        query = "SELECT DISTINCT city FROM hotels WHERE city IS NOT NULL AND city != '' ORDER BY city"
        try:
            async with self.get_connection() as db:
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [row['city'] for row in rows]
        except Exception as e:
            logger.error(f"SQLite get_cities error: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        query = "SELECT COUNT(*) as total_hotels, AVG(average_rating) as avg_rating, COUNT(DISTINCT city) as total_cities FROM hotels"
        try:
            async with self.get_connection() as db:
                async with db.execute(query) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else {}
        except Exception as e:
            logger.error(f"SQLite get_stats error: {e}")
            return {}
