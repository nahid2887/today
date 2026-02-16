"""
Vector Store Manager for Hotel Data.

This module handles ChromaDB operations including:
- Syncing hotel data from the backend API
- Creating embeddings from hotel information
- Performing hybrid searches (city filtering + semantic search)
"""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import (
    HOTEL_SYNC_ENDPOINT,
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    REQUEST_TIMEOUT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorManager:
    """
    Manages vector storage and retrieval for hotel recommendations.
    
    This class handles:
    - Fetching hotel data from the backend API
    - Creating embeddings from hotel metadata
    - Storing vectors in ChromaDB
    - Performing hybrid searches with city filters
    """
    
    def __init__(self):
        """Initialize the Vector Manager with ChromaDB and embeddings."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.Client(Settings(
            persist_directory=CHROMA_PERSIST_DIR,
            anonymized_telemetry=False
        ))
        
        self.vector_store: Optional[Chroma] = None
        logger.info("VectorManager initialized")
    
    def _create_embedding_string(self, hotel: Dict[str, Any]) -> str:
        """
        Create a searchable embedding string from hotel data.
        
        Format: "Hotel: {hotel_name} in {city}. {description}. Features: {amenities}"
        
        Args:
            hotel: Hotel data dictionary
            
        Returns:
            Formatted string for embedding
        """
        # Handle both 'name' and 'hotel_name' keys
        hotel_name = hotel.get("hotel_name") or hotel.get("name", "Unknown Hotel")
        city = hotel.get("city") or "Unknown City"
        description = hotel.get("description") or ""
        amenities = hotel.get("amenities", [])
        
        # Join amenities into a comma-separated string
        amenities_str = ", ".join(amenities) if isinstance(amenities, list) else str(amenities)
        
        embedding_text = f"Hotel: {hotel_name} in {city}. {description}. Features: {amenities_str}"
        
        return embedding_text
    
    async def sync_hotels(self) -> Dict[str, Any]:
        """
        Fetch hotel data from the sync endpoint and populate ChromaDB.
        
        This method:
        1. Fetches all hotels from the backend API
        2. Creates embedding strings for each hotel
        3. Stores vectors with metadata in ChromaDB
        
        Returns:
            Dictionary containing sync status and count
            
        Raises:
            httpx.RequestError: If the API request fails
        """
        logger.info(f"Starting hotel sync from {HOTEL_SYNC_ENDPOINT}")
        
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(HOTEL_SYNC_ENDPOINT)
                response.raise_for_status()
                hotels_data = response.json()
            
            # Debug: Log the response structure
            logger.info(f"API Response type: {type(hotels_data)}")
            if isinstance(hotels_data, dict):
                logger.info(f"Response keys: {hotels_data.keys()}")
            
            # Handle different response formats
            if isinstance(hotels_data, dict) and "hotels" in hotels_data:
                hotels = hotels_data["hotels"]
            elif isinstance(hotels_data, list):
                hotels = hotels_data
            else:
                logger.error(f"Unexpected data format: {type(hotels_data)}")
                logger.error(f"Response content: {str(hotels_data)[:500]}")
                return {"status": "error", "message": "Unexpected data format", "count": 0}
            
            if not hotels:
                logger.warning("No hotels found in sync response")
                return {"status": "warning", "message": "No hotels to sync", "count": 0}
            
            logger.info(f"Processing {len(hotels)} hotels from API")
            
            # Prepare documents and metadata for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for idx, hotel in enumerate(hotels):
                try:
                    # Validate hotel data
                    if hotel is None:
                        logger.warning(f"Skipping None hotel at index {idx}")
                        continue
                    
                    # Validate required fields
                    if not hotel.get('id'):
                        logger.warning(f"Skipping hotel without ID at index {idx}")
                        continue
                    
                    # Create embedding string
                    embedding_text = self._create_embedding_string(hotel)
                    documents.append(embedding_text)
                    
                    # Extract city - fallback to location if city is empty
                    city = hotel.get("city", "").strip()
                    if not city:
                        # Try to extract city from location field
                        location = hotel.get("location", "")
                        if location:
                            # Simple heuristic: use location as city if it's a single word or known city
                            city = location.strip().split(',')[0].strip()
                    
                    # Extract and store metadata
                    metadata = {
                        "id": str(hotel.get("id", "")),
                        "hotel_name": hotel.get("hotel_name") or hotel.get("name", "Unknown"),
                        "city": str(city or "unknown").lower(),  # Lowercase for exact matching
                        "average_rating": float(hotel.get("average_rating") or 0.0) if isinstance(hotel.get("average_rating"), (int, float)) else float(str(hotel.get("average_rating", "0.0")).replace(",", ".")),
                        "total_ratings": int(hotel.get("total_ratings", 0)),
                        "description": str(hotel.get("description") or "")[:500],  # Truncate for metadata
                        "location": hotel.get("location", ""),
                        "country": hotel.get("country", ""),
                        "room_type": str(hotel.get("room_type", "")).lower(),  # Store room type for filtering
                        "number_of_rooms": int(hotel.get("number_of_rooms", 0)),  # Store hotel size
                        "amenities": ", ".join(hotel.get("amenities", [])) if hotel.get("amenities") else "",  # Join array to string
                    }
                    metadatas.append(metadata)
                    
                    # Use hotel ID as the document ID
                    ids.append(f"hotel_{hotel.get('id', idx)}")
                    
                except Exception as e:
                    logger.error(f"Error processing hotel at index {idx}: {e}")
                    logger.error(f"Hotel data: {hotel}")
                    continue
            
            # Delete existing collection if it exists and create new one
            try:
                self.chroma_client.delete_collection(name=COLLECTION_NAME)
                logger.info(f"Deleted existing collection: {COLLECTION_NAME}")
            except Exception as e:
                logger.info(f"No existing collection to delete: {e}")
            
            # Create vector store with Langchain wrapper
            self.vector_store = Chroma.from_texts(
                texts=documents,
                embedding=self.embeddings,
                metadatas=metadatas,
                ids=ids,
                collection_name=COLLECTION_NAME,
                persist_directory=CHROMA_PERSIST_DIR
            )
            
            logger.info(f"Successfully synced {len(hotels)} hotels to ChromaDB")
            
            return {
                "status": "success",
                "message": f"Synced {len(hotels)} hotels",
                "count": len(hotels)
            }
            
        except httpx.RequestError as e:
            logger.error(f"Failed to fetch hotels from API: {e}")
            return {
                "status": "error",
                "message": f"API request failed: {str(e)}",
                "count": 0
            }
        except Exception as e:
            logger.error(f"Error during hotel sync: {e}")
            return {
                "status": "error",
                "message": f"Sync failed: {str(e)}",
                "count": 0
            }
    
    def search_hotels(
        self,
        query: str,
        city: Optional[str] = None,
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search on hotels.
        
        Args:
            query: Natural language search query
            city: Optional city filter for exact match
            k: Number of results to return
            
        Returns:
            List of hotel dictionaries with similarity scores
        """
        if self.vector_store is None:
            # Try to load existing vector store
            try:
                self.vector_store = Chroma(
                    collection_name=COLLECTION_NAME,
                    embedding_function=self.embeddings,
                    persist_directory=CHROMA_PERSIST_DIR
                )
            except Exception as e:
                logger.error(f"Vector store not initialized: {e}")
                return []
        
        try:
            # Build filter for city if provided
            where_filter = None
            if city:
                where_filter = {"city": city.lower()}
            
            # Perform similarity search with metadata filter
            results = self.vector_store.similarity_search_with_score(
                query,
                k=k,
                filter=where_filter
            )
            
            # Format results with similarity scores
            formatted_results = []
            for doc, score in results:
                hotel_data = {
                    "id": doc.metadata.get("id"),
                    "hotel_name": doc.metadata.get("hotel_name"),
                    "city": doc.metadata.get("city"),
                    "average_rating": doc.metadata.get("average_rating", 0.0),
                    "total_ratings": doc.metadata.get("total_ratings", 0),
                    "description": doc.metadata.get("description", ""),
                    "location": doc.metadata.get("location", ""),
                    "country": doc.metadata.get("country", ""),
                    "room_type": doc.metadata.get("room_type", ""),
                    "number_of_rooms": doc.metadata.get("number_of_rooms", 0),
                    "amenities": doc.metadata.get("amenities", ""),  # Important for filtering
                    "similarity_score": float(1 - score) if score <= 1 else float(1 / (1 + score)),  # Convert distance to similarity
                    "content": doc.page_content
                }
                formatted_results.append(hotel_data)
            
            logger.info(f"Found {len(formatted_results)} hotels for query: '{query}'" + (f" in {city}" if city else ""))
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_collection_count(self) -> int:
        """Get the total number of hotels in the vector store."""
        try:
            # Try to load the vector store if not already loaded
            if self.vector_store is None:
                try:
                    self.vector_store = Chroma(
                        collection_name=COLLECTION_NAME,
                        embedding_function=self.embeddings,
                        persist_directory=CHROMA_PERSIST_DIR
                    )
                except Exception:
                    # Collection doesn't exist yet
                    return 0
            
            # Get collection directly from the vector store
            collection = self.vector_store._collection
            count = collection.count()
            logger.info(f"Collection count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error getting collection count: {e}")
            return 0
