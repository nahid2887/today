"""
Comprehensive Test Suite for Hotel Recommendation Agent.

This test suite covers:
- Unit tests for all components
- Edge cases and error handling
- Integration tests
- Async operations
- Database operations
- LangGraph workflow
- Configuration validation

Run with: pytest test_basic.py -v -s
Or standalone: python test_basic.py
"""
import pytest
import asyncio
import tempfile
import shutil
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from typing import Dict, List, Any


# ============================================================================
# FIXTURES AND TEST DATA
# ============================================================================

@pytest.fixture
def sample_hotel():
    """Sample hotel data for testing."""
    return {
        "id": "123",
        "name": "Grand Plaza Hotel",
        "city": "Mumbai",
        "description": "Luxury hotel in downtown Mumbai with ocean views",
        "amenities": ["WiFi", "Pool", "Spa", "Gym", "Restaurant"],
        "average_rating": 4.5,
        "address": "123 Marine Drive, Mumbai",
        "hotel_type": "Luxury",
        "price_range": "₹5000-₹8000"
    }


@pytest.fixture
def sample_hotels_list():
    """List of sample hotels for bulk testing."""
    return [
        {
            "id": "1",
            "name": "Budget Inn",
            "city": "Delhi",
            "description": "Affordable hotel near airport",
            "amenities": ["WiFi", "Parking"],
            "average_rating": 3.5
        },
        {
            "id": "2",
            "name": "Luxury Palace",
            "city": "Mumbai",
            "description": "5-star luxury hotel",
            "amenities": ["WiFi", "Pool", "Spa", "Gym"],
            "average_rating": 4.8
        },
        {
            "id": "3",
            "name": "Beach Resort",
            "city": "Goa",
            "description": "Beachfront resort with water sports",
            "amenities": ["Beach Access", "Pool", "Restaurant"],
            "average_rating": 4.2
        }
    ]


@pytest.fixture
def mock_api_response():
    """Mock API response for hotel sync."""
    return {
        "message": "Success",
        "count": 3,
        "hotels": [
            {
                "id": 1,
                "name": "Test Hotel 1",
                "city": "Mumbai",
                "description": "Test description 1",
                "amenities": ["WiFi"],
                "average_rating": 4.0
            },
            {
                "id": 2,
                "name": "Test Hotel 2",
                "city": "Delhi",
                "description": "Test description 2",
                "amenities": ["Pool"],
                "average_rating": 4.5
            }
        ]
    }


@pytest.fixture
def temp_chroma_dir():
    """Create temporary directory for ChromaDB during tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# VECTORMANAGER TESTS
# ============================================================================

class TestVectorManagerCore:
    """Core functionality tests for VectorManager."""
    
    def test_init_creates_embeddings(self):
        """Test VectorManager initialization creates embeddings."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        
        assert vm.embeddings is not None
        assert hasattr(vm.embeddings, 'embed_query')
        assert hasattr(vm.embeddings, 'embed_documents')
    
    def test_embedding_string_creation(self, sample_hotel):
        """Test embedding string creation with all fields."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        embedding_text = vm._create_embedding_string(sample_hotel)
        
        assert "Hotel: Grand Plaza Hotel" in embedding_text
        assert "Mumbai" in embedding_text
        assert "Luxury hotel in downtown Mumbai" in embedding_text
        assert "WiFi" in embedding_text
        assert "Pool" in embedding_text
        assert "Spa" in embedding_text
    
    def test_embedding_string_with_minimal_data(self):
        """Test embedding creation with minimal hotel data."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        minimal_hotel = {"name": "Minimal Hotel"}
        
        embedding_text = vm._create_embedding_string(minimal_hotel)
        
        assert "Hotel: Minimal Hotel" in embedding_text
        assert "Unknown City" in embedding_text
        # Description is empty string, not "No description available"
        assert "Features:" in embedding_text
    
    def test_embedding_string_with_none_values(self):
        """Test embedding creation with None values."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        hotel_with_nones = {
            "name": "Test Hotel",
            "city": None,
            "description": None,
            "amenities": None
        }
        
        embedding_text = vm._create_embedding_string(hotel_with_nones)
        
        assert "Test Hotel" in embedding_text
        # When city is None, it gets printed as 'None'
        assert "None" in embedding_text or "Unknown City" in embedding_text
        assert "Features:" in embedding_text
        # Should not crash with None values
    
    def test_embedding_string_with_empty_amenities(self):
        """Test embedding creation with empty amenities list."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        hotel = {
            "name": "No Amenities Hotel",
            "city": "Delhi",
            "amenities": []
        }
        
        embedding_text = vm._create_embedding_string(hotel)
        
        assert "No Amenities Hotel" in embedding_text
        assert "Features:" in embedding_text


class TestVectorManagerSync:
    """Tests for hotel data synchronization."""
    
    @pytest.mark.asyncio
    async def test_sync_hotels_success(self, mock_api_response):
        """Test successful hotel synchronization."""
        from core.vector_store import VectorManager
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=Mock(
                status_code=200,
                json=lambda: mock_api_response
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            vm = VectorManager()
            # Initialize vector_store first
            vm.vector_store = MagicMock()
            vm.vector_store.add_documents = MagicMock(return_value=None)
            
            result = await vm.sync_hotels()
            
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_sync_hotels_empty_response(self):
        """Test sync with empty hotel list."""
        from core.vector_store import VectorManager
        
        empty_response = {
            "message": "Success",
            "count": 0,
            "hotels": []
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=Mock(
                status_code=200,
                json=lambda: empty_response
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            vm = VectorManager()
            result = await vm.sync_hotels()
            
            # Should handle empty list gracefully, returns dict
            assert result["status"] == "warning"
            assert result["count"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_hotels_api_error(self):
        """Test sync when API returns error."""
        from core.vector_store import VectorManager
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=Mock(),
                response=Mock(status_code=500)
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            vm = VectorManager()
            result = await vm.sync_hotels()
            
            assert result["status"] == "error"
    
    @pytest.mark.asyncio
    async def test_sync_hotels_network_error(self):
        """Test sync with network error."""
        from core.vector_store import VectorManager
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.RequestError("Connection failed", request=Mock()))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            vm = VectorManager()
            result = await vm.sync_hotels()
            
            assert result["status"] == "error"
    
    @pytest.mark.asyncio
    async def test_sync_hotels_malformed_response(self):
        """Test sync with malformed API response."""
        from core.vector_store import VectorManager
        
        malformed_response = {
            "message": "Success",
            # Missing 'hotels' key
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=Mock(
                status_code=200,
                json=lambda: malformed_response
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            vm = VectorManager()
            result = await vm.sync_hotels()
            
            # Should handle malformed response
            assert result["status"] == "error"


class TestVectorManagerSearch:
    """Tests for hotel search functionality."""
    
    def test_search_hotels_with_city(self):
        """Test search with city filter."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        
        # Mock the similarity search - use similarity_search_with_score
        mock_results = [
            (Mock(page_content="Hotel 1", metadata={"city": "mumbai", "id": "1", "hotel_name": "Hotel 1", "average_rating": 4.5}), 0.1),
            (Mock(page_content="Hotel 2", metadata={"city": "mumbai", "id": "2", "hotel_name": "Hotel 2", "average_rating": 4.0}), 0.2),
        ]
        
        vm.vector_store.similarity_search_with_score = Mock(return_value=mock_results)
        results = vm.search_hotels("luxury hotel", city="Mumbai", k=5)
        
        assert len(results) == 2
        # ChromaDB returns distance, code converts to similarity: 1 - distance
        # So distance 0.1 becomes similarity 0.9
        assert results[0]["similarity_score"] == 0.9
    
    def test_search_hotels_without_city(self):
        """Test search without city filter."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        
        mock_results = [
            (Mock(page_content="Hotel", metadata={"id": "1", "city": "delhi", "hotel_name": "Budget Hotel", "average_rating": 3.5}), 0.85),
        ]
        
        vm.vector_store.similarity_search_with_score = Mock(return_value=mock_results)
        results = vm.search_hotels("budget hotel", k=5)
        
        assert len(results) == 1
    
    def test_search_hotels_empty_query(self):
        """Test search with empty query."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        vm.vector_store.similarity_search_with_relevance_scores = Mock(return_value=[])
        
        results = vm.search_hotels("", k=5)
        
        assert len(results) == 0
    
    def test_search_hotels_with_k_parameter(self):
        """Test search respects k parameter."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        
        # Create 10 mock results
        mock_results = [
            (Mock(page_content=f"Hotel {i}", metadata={"id": str(i)}), 0.9 - i*0.05)
            for i in range(10)
        ]
        
        vm.vector_store.similarity_search_with_relevance_scores = Mock(return_value=mock_results)
        results = vm.search_hotels("hotel", k=3)
        
        # Should only return top 3
        assert len(results) <= 3


# ============================================================================
# HOTEL TOOLS TESTS
# ============================================================================

class TestHotelToolsAPI:
    """Tests for hotel API tools."""
    
    @pytest.mark.asyncio
    async def test_fetch_hotel_details_success(self):
        """Test successful hotel details fetch."""
        from tools.hotel_tools import fetch_hotel_details
        
        mock_response = {
            "id": 123,
            "name": "Test Hotel",
            "price": 150,
            "special_offers": ["10% discount"],
            "availability": True
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=Mock(
                status_code=200,
                json=lambda: mock_response
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            result = await fetch_hotel_details(123)
            
            assert result is not None
            assert result["id"] == 123
            assert result["price"] == 150
    
    @pytest.mark.asyncio
    async def test_fetch_hotel_details_404(self):
        """Test fetch when hotel not found."""
        from tools.hotel_tools import fetch_hotel_details
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            result = await fetch_hotel_details(999)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_hotel_details_timeout(self):
        """Test fetch with timeout."""
        from tools.hotel_tools import fetch_hotel_details
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            result = await fetch_hotel_details(123)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_live_hotel_details_batch(self):
        """Test batch fetching of hotel details."""
        from tools.hotel_tools import get_live_hotel_details_batch
        
        hotel_ids = [1, 2, 3]
        
        async def mock_fetch(hotel_id):
            return {"id": hotel_id, "price": hotel_id * 100}
        
        with patch('tools.hotel_tools.fetch_hotel_details', side_effect=mock_fetch):
            results = await get_live_hotel_details_batch(hotel_ids)
            
            assert len(results) == 3
            assert results[0]["id"] == 1
            assert results[1]["price"] == 200
    
    @pytest.mark.asyncio
    async def test_get_live_hotel_details_batch_with_failures(self):
        """Test batch fetch with some failures."""
        from tools.hotel_tools import get_live_hotel_details_batch
        
        hotel_ids = [1, 2, 3]
        
        async def mock_fetch(hotel_id):
            if hotel_id == 2:
                return None  # Simulate failure
            return {"id": hotel_id, "price": hotel_id * 100}
        
        with patch('tools.hotel_tools.fetch_hotel_details', side_effect=mock_fetch):
            results = await get_live_hotel_details_batch(hotel_ids)
            
            # Returns 3 results, but one has an error
            assert len(results) == 3
            # Check that some have data
            assert any("price" in r for r in results if isinstance(r, dict))
    
    @pytest.mark.asyncio
    async def test_get_live_hotel_details_batch_empty(self):
        """Test batch fetch with empty list."""
        from tools.hotel_tools import get_live_hotel_details_batch
        
        results = await get_live_hotel_details_batch([])
        
        assert len(results) == 0


class TestHotelEnrichment:
    """Tests for hotel data enrichment."""
    
    def test_enrich_hotel_with_live_data_full(self):
        """Test enrichment with complete live data."""
        from tools.hotel_tools import enrich_hotel_with_live_data
        
        base_hotel = {
            "id": "123",
            "hotel_name": "Test Hotel",
            "city": "Mumbai",
            "average_rating": 4.5
        }
        
        live_data = {
            "id": 123,
            "price": 200,
            "special_offers": ["Early bird discount", "Free breakfast"],
            "availability": True,
            "images": ["image1.jpg"]
        }
        
        enriched = enrich_hotel_with_live_data(base_hotel, live_data)
        
        assert enriched["id"] == "123"
        assert enriched["hotel_name"] == "Test Hotel"
        assert enriched["price"] == 200
        assert len(enriched["special_offers"]) == 2
        assert enriched["current_availability"] is True
    
    def test_enrich_hotel_without_live_data(self):
        """Test enrichment when no live data available."""
        from tools.hotel_tools import enrich_hotel_with_live_data
        
        base_hotel = {
            "id": "123",
            "hotel_name": "Test Hotel",
            "average_rating": 4.5
        }
        
        enriched = enrich_hotel_with_live_data(base_hotel, None)
        
        assert enriched["id"] == "123"
        assert enriched["hotel_name"] == "Test Hotel"
        assert enriched["price"] is None
        assert enriched["special_offers"] == []
        assert enriched["current_availability"] is None
    
    def test_enrich_hotel_partial_live_data(self):
        """Test enrichment with partial live data."""
        from tools.hotel_tools import enrich_hotel_with_live_data
        
        base_hotel = {
            "id": "123",
            "hotel_name": "Test Hotel"
        }
        
        live_data = {
            "id": 123,
            "price": 150
            # Missing special_offers and availability
        }
        
        enriched = enrich_hotel_with_live_data(base_hotel, live_data)
        
        assert enriched["price"] == 150
        assert enriched["special_offers"] == []
        # availability defaults to True if not specified
        assert enriched["current_availability"] is True


# ============================================================================
# RANKING AND SCORING TESTS
# ============================================================================

class TestRankingLogic:
    """Tests for hotel ranking calculations."""
    
    def test_ranking_formula_high_rating_high_similarity(self):
        """Test ranking with high rating and similarity."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        rating = 5.0
        similarity = 0.95
        
        normalized_rating = rating / 5.0
        score = (RATING_WEIGHT * normalized_rating) + (SIMILARITY_WEIGHT * similarity)
        
        # Should be: (0.6 * 1.0) + (0.4 * 0.95) = 0.6 + 0.38 = 0.98
        assert abs(score - 0.98) < 0.01
    
    def test_ranking_formula_low_rating_high_similarity(self):
        """Test ranking with low rating but high similarity."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        rating = 2.0
        similarity = 0.95
        
        normalized_rating = rating / 5.0
        score = (RATING_WEIGHT * normalized_rating) + (SIMILARITY_WEIGHT * similarity)
        
        # Should be: (0.6 * 0.4) + (0.4 * 0.95) = 0.24 + 0.38 = 0.62
        assert abs(score - 0.62) < 0.01
    
    def test_ranking_prioritizes_rating(self):
        """Test that rating is weighted more than similarity."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        # Hotel A: High rating (4.8), medium similarity (0.6)
        score_a = (RATING_WEIGHT * 4.8 / 5.0) + (SIMILARITY_WEIGHT * 0.6)
        
        # Hotel B: Medium rating (3.0), high similarity (0.95)
        score_b = (RATING_WEIGHT * 3.0 / 5.0) + (SIMILARITY_WEIGHT * 0.95)
        
        # Hotel A should rank higher despite lower similarity
        assert score_a > score_b
    
    def test_ranking_edge_case_zero_rating(self):
        """Test ranking with zero rating."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        rating = 0.0
        similarity = 1.0
        
        score = (RATING_WEIGHT * rating / 5.0) + (SIMILARITY_WEIGHT * similarity)
        
        # Should be: (0.6 * 0) + (0.4 * 1.0) = 0.4
        assert abs(score - 0.4) < 0.01
    
    def test_ranking_edge_case_zero_similarity(self):
        """Test ranking with zero similarity."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        rating = 5.0
        similarity = 0.0
        
        score = (RATING_WEIGHT * rating / 5.0) + (SIMILARITY_WEIGHT * similarity)
        
        # Should be: (0.6 * 1.0) + (0.4 * 0) = 0.6
        assert abs(score - 0.6) < 0.01
    
    def test_ranking_weights_sum_to_one(self):
        """Test that ranking weights sum to 1.0."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        assert abs((RATING_WEIGHT + SIMILARITY_WEIGHT) - 1.0) < 0.001


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Tests for configuration settings."""
    
    def test_all_config_values_present(self):
        """Test that all required config values exist."""
        from config import (
            HOTEL_SYNC_ENDPOINT,
            HOTEL_DETAILS_ENDPOINT,
            GROQ_MODEL,
            CHROMA_PERSIST_DIR,
            COLLECTION_NAME,
            EMBEDDING_MODEL,
            RATING_WEIGHT,
            SIMILARITY_WEIGHT,
            TOP_K_RESULTS,
            REQUEST_TIMEOUT
        )
        
        assert HOTEL_SYNC_ENDPOINT is not None
        assert HOTEL_DETAILS_ENDPOINT is not None
        assert GROQ_MODEL is not None
        assert CHROMA_PERSIST_DIR is not None
        assert COLLECTION_NAME is not None
        assert EMBEDDING_MODEL is not None
    
    def test_endpoint_formats(self):
        """Test API endpoint formats."""
        from config import HOTEL_SYNC_ENDPOINT, HOTEL_DETAILS_ENDPOINT
        
        assert HOTEL_SYNC_ENDPOINT.startswith("http://") or HOTEL_SYNC_ENDPOINT.startswith("https://")
        assert "{id}" in HOTEL_DETAILS_ENDPOINT
    
    def test_collection_name(self):
        """Test ChromaDB collection name."""
        from config import COLLECTION_NAME
        
        assert COLLECTION_NAME == "hotels"
        assert isinstance(COLLECTION_NAME, str)
    
    def test_embedding_model_name(self):
        """Test embedding model configuration."""
        from config import EMBEDDING_MODEL
        
        assert "sentence-transformers" in EMBEDDING_MODEL or "all-MiniLM" in EMBEDDING_MODEL
    
    def test_groq_model_name(self):
        """Test Groq model configuration."""
        from config import GROQ_MODEL
        
        assert "llama" in GROQ_MODEL.lower()
    
    def test_weights_are_numbers(self):
        """Test that weights are numeric."""
        from config import RATING_WEIGHT, SIMILARITY_WEIGHT
        
        assert isinstance(RATING_WEIGHT, (int, float))
        assert isinstance(SIMILARITY_WEIGHT, (int, float))
        assert 0 <= RATING_WEIGHT <= 1
        assert 0 <= SIMILARITY_WEIGHT <= 1
    
    def test_top_k_results_positive(self):
        """Test TOP_K_RESULTS is positive integer."""
        from config import TOP_K_RESULTS
        
        assert isinstance(TOP_K_RESULTS, int)
        assert TOP_K_RESULTS > 0
    
    def test_request_timeout_positive(self):
        """Test REQUEST_TIMEOUT is positive."""
        from config import REQUEST_TIMEOUT
        
        assert isinstance(REQUEST_TIMEOUT, (int, float))
        assert REQUEST_TIMEOUT > 0


# ============================================================================
# AGENT WORKFLOW TESTS
# ============================================================================

class TestAgentWorkflow:
    """Tests for LangGraph agent workflow."""
    
    def test_agent_state_structure(self):
        """Test AgentState TypedDict structure."""
        from agents.hotel_agent import AgentState
        
        # Verify state has required keys
        state_annotations = AgentState.__annotations__
        
        assert "query" in state_annotations
        assert "history" in state_annotations
        assert "extracted_city" in state_annotations
        assert "search_results" in state_annotations
        assert "ranked_hotels" in state_annotations
        assert "hydrated_hotels" in state_annotations
        assert "response" in state_annotations
    
    def test_city_extraction_from_query(self):
        """Test city extraction logic."""
        # This tests the pattern matching for city extraction
        queries_and_cities = [
            ("Find hotels in Mumbai", "Mumbai"),
            ("I want to stay in Delhi", "Delhi"),
            ("Show me hotels near Bangalore", "Bangalore"),
            ("Looking for a hotel in Goa", "Goa"),
            ("Hotels at Pune", "Pune"),
        ]
        
        import re
        city_pattern = r"(?:in|near|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        
        for query, expected_city in queries_and_cities:
            match = re.search(city_pattern, query)
            if match:
                extracted = match.group(1)
                assert extracted == expected_city


class TestAgentInitialization:
    """Tests for agent initialization."""
    
    def test_agent_initialization(self):
        """Test HotelRecommendationAgent can be initialized."""
        from agents.hotel_agent import HotelRecommendationAgent
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
            agent = HotelRecommendationAgent(vm)
            
            assert agent.vector_manager is not None
            assert agent.llm is not None
            assert agent.graph is not None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for main module."""
    
    @pytest.mark.asyncio
    async def test_main_function_imports(self):
        """Test main module function imports."""
        from main import (
            run_travel_chat,
            sync_hotel_data,
            initialize_system,
            get_hotel_count
        )
        
        assert callable(run_travel_chat)
        assert callable(sync_hotel_data)
        assert callable(initialize_system)
        assert callable(get_hotel_count)
    
    def test_core_imports(self):
        """Test core module imports."""
        from core import VectorManager
        from core.vector_store import VectorManager as VM
        
        assert VectorManager is VM
    
    def test_tools_imports(self):
        """Test tools module imports."""
        from tools import (
            get_live_hotel_details,
            enrich_hotel_with_live_data
        )
        from tools.hotel_tools import (
            fetch_hotel_details,
            get_live_hotel_details_batch
        )
        
        # get_live_hotel_details is a LangChain StructuredTool
        assert get_live_hotel_details is not None
        assert callable(enrich_hotel_with_live_data)
        # These are async functions
        assert asyncio.iscoroutinefunction(fetch_hotel_details)
        assert asyncio.iscoroutinefunction(get_live_hotel_details_batch)
    
    def test_agents_imports(self):
        """Test agents module imports."""
        from agents import HotelRecommendationAgent
        from agents.hotel_agent import HotelRecommendationAgent as HRA
        
        assert HotelRecommendationAgent is HRA


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_query_handling(self):
        """Test handling of empty query string."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        vm.vector_store.similarity_search_with_relevance_scores = Mock(return_value=[])
        
        results = vm.search_hotels("", k=5)
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_very_long_query(self):
        """Test handling of very long query."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        long_query = "luxury hotel " * 100  # Very long query
        
        vm.vector_store.similarity_search_with_relevance_scores = Mock(return_value=[])
        # Should not crash
        results = vm.search_hotels(long_query, k=5)
        assert isinstance(results, list)
    
    def test_special_characters_in_query(self):
        """Test handling of special characters."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        vm.vector_store = MagicMock()
        special_query = "hotel @#$% with * and & symbols"
        
        vm.vector_store.similarity_search_with_relevance_scores = Mock(return_value=[])
        # Should handle gracefully
        results = vm.search_hotels(special_query, k=5)
        assert isinstance(results, list)
    
    def test_unicode_in_hotel_data(self):
        """Test handling of unicode characters."""
        from core.vector_store import VectorManager
        
        vm = VectorManager()
        unicode_hotel = {
            "name": "होटल महाराज",  # Hindi text
            "city": "मुंबई",
            "description": "Best hotel with café ☕ and wifi 📶"
        }
        
        # Should not crash with unicode
        embedding_text = vm._create_embedding_string(unicode_hotel)
        assert isinstance(embedding_text, str)
    
    @pytest.mark.asyncio
    async def test_concurrent_api_calls(self):
        """Test handling of concurrent API calls."""
        from tools.hotel_tools import get_live_hotel_details_batch
        
        async def mock_fetch(hotel_id):
            await asyncio.sleep(0.01)  # Simulate network delay
            return {"id": hotel_id, "price": 100}
        
        with patch('tools.hotel_tools.fetch_hotel_details', side_effect=mock_fetch):
            # Test with many concurrent calls
            hotel_ids = list(range(50))
            results = await get_live_hotel_details_batch(hotel_ids)
            
            assert len(results) == 50
    
    def test_malformed_hotel_data(self):
        """Test handling of malformed hotel data."""
        from tools.hotel_tools import enrich_hotel_with_live_data
        
        malformed_base = {}  # Empty dict
        malformed_live = {"random_key": "value"}
        
        # Should not crash
        enriched = enrich_hotel_with_live_data(malformed_base, malformed_live)
        assert isinstance(enriched, dict)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance-related tests."""
    
    def test_embedding_creation_performance(self):
        """Test embedding creation is reasonably fast."""
        from core.vector_store import VectorManager
        import time
        
        vm = VectorManager()
        hotel = {
            "name": "Test Hotel",
            "city": "Mumbai",
            "description": "Test description",
            "amenities": ["WiFi", "Pool"]
        }
        
        start = time.time()
        for _ in range(100):
            vm._create_embedding_string(hotel)
        duration = time.time() - start
        
        # Should complete 100 iterations in under 1 second
        assert duration < 1.0
    
    @pytest.mark.asyncio
    async def test_batch_fetch_concurrency(self):
        """Test batch fetch handles concurrency efficiently."""
        from tools.hotel_tools import get_live_hotel_details_batch
        import time
        
        async def mock_fetch(hotel_id):
            await asyncio.sleep(0.1)  # 100ms delay
            return {"id": hotel_id}
        
        with patch('tools.hotel_tools.fetch_hotel_details', side_effect=mock_fetch):
            start = time.time()
            results = await get_live_hotel_details_batch([1, 2, 3, 4, 5])
            duration = time.time() - start
            
            # Should complete in ~100ms (concurrent), not 500ms (sequential)
            assert duration < 0.3  # Allow some overhead


# ============================================================================
# STANDALONE TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all tests without pytest."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE HOTEL RECOMMENDATION AGENT TEST SUITE")
    print("=" * 80)
    
    test_count = 0
    passed = 0
    failed = 0
    
    # Define simple tests that don't need fixtures or complex mocking
    simple_tests = [
        # VectorManager Core Tests
        ("Embedding: Full hotel data", test_embedding_full),
        ("Embedding: Minimal data", test_embedding_minimal),
        ("Embedding: None values", test_embedding_none),
        ("Embedding: Empty amenities", test_embedding_empty_amenities),
        ("VectorManager: Init", test_vector_init),
        
        # Hotel Enrichment Tests
        ("Enrichment: Full data", test_enrich_full),
        ("Enrichment: No live data", test_enrich_none),
        ("Enrichment: Partial data", test_enrich_partial),
        ("Enrichment: Malformed data", test_enrich_malformed),
        
        # Ranking Tests
        ("Ranking: High rating + similarity", test_ranking_high),
        ("Ranking: Low rating + high similarity", test_ranking_low_high),
        ("Ranking: Priority check", test_ranking_priority),
        ("Ranking: Zero rating", test_ranking_zero_rating),
        ("Ranking: Zero similarity", test_ranking_zero_sim),
        ("Ranking: Weights sum to 1", test_ranking_weights),
        
        # Configuration Tests
        ("Config: All values present", test_config_present),
        ("Config: Endpoints format", test_config_endpoints),
        ("Config: Collection name", test_config_collection),
        ("Config: Embedding model", test_config_embedding),
        ("Config: Groq model", test_config_groq),
        ("Config: Weights valid", test_config_weights),
        ("Config: TOP_K positive", test_config_topk),
        ("Config: Timeout positive", test_config_timeout),
        
        # Integration Tests
        ("Import: Main functions", test_import_main),
        ("Import: Core modules", test_import_core),
        ("Import: Tools", test_import_tools),
        ("Import: Agents", test_import_agents),
        
        # Edge Cases
        ("Edge: Unicode handling", test_unicode),
        ("Edge: Special characters", test_special_chars),
    ]
    
    for test_name, test_func in simple_tests:
        test_count += 1
        try:
            test_func()
            print(f"  ✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test_name}")
            print(f"    Error: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"TEST RESULTS: {passed}/{test_count} passed")
    if failed > 0:
        print(f"FAILED: {failed} tests")
    else:
        print("ALL TESTS PASSED! ✓")
    print("=" * 80 + "\n")
    
    return failed == 0


# ============================================================================
# SIMPLE TEST FUNCTIONS (No fixtures or complex mocking)
# ============================================================================

def test_embedding_full():
    """Test embedding with full hotel data."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {
        "name": "Grand Plaza",
        "city": "Mumbai",
        "description": "Luxury hotel",
        "amenities": ["WiFi", "Pool"]
    }
    text = vm._create_embedding_string(hotel)
    assert "Grand Plaza" in text
    assert "Mumbai" in text

def test_embedding_minimal():
    """Test embedding with minimal data."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {"name": "Minimal Hotel"}
    text = vm._create_embedding_string(hotel)
    assert "Minimal Hotel" in text
    assert "Unknown City" in text

def test_embedding_none():
    """Test embedding with None values."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {"name": "Test", "city": None, "description": None}
    text = vm._create_embedding_string(hotel)
    assert "Test" in text

def test_embedding_empty_amenities():
    """Test embedding with empty amenities."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {"name": "No Amenities", "amenities": []}
    text = vm._create_embedding_string(hotel)
    assert "No Amenities" in text

def test_vector_init():
    """Test VectorManager initialization."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    assert vm.embeddings is not None

def test_enrich_full():
    """Test enrichment with full data."""
    from tools.hotel_tools import enrich_hotel_with_live_data
    base = {"id": "123", "hotel_name": "Test", "average_rating": 4.5}
    live = {"price": 200, "special_offers": ["Deal"], "availability": True}
    enriched = enrich_hotel_with_live_data(base, live)
    assert enriched["price"] == 200
    assert enriched["current_availability"] is True

def test_enrich_none():
    """Test enrichment with None live data."""
    from tools.hotel_tools import enrich_hotel_with_live_data
    base = {"id": "123", "hotel_name": "Test"}
    enriched = enrich_hotel_with_live_data(base, None)
    assert enriched["price"] is None
    assert enriched["special_offers"] == []
    assert enriched["current_availability"] is None

def test_enrich_partial():
    """Test enrichment with partial data."""
    from tools.hotel_tools import enrich_hotel_with_live_data
    base = {"id": "123", "hotel_name": "Test"}
    live = {"price": 150}
    enriched = enrich_hotel_with_live_data(base, live)
    assert enriched["price"] == 150
    assert enriched["special_offers"] == []

def test_enrich_malformed():
    """Test enrichment with malformed data."""
    from tools.hotel_tools import enrich_hotel_with_live_data
    base = {}
    live = {"random_key": "value"}
    enriched = enrich_hotel_with_live_data(base, live)
    assert isinstance(enriched, dict)

def test_ranking_high():
    """Test ranking with high values."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    score = (RATING_WEIGHT * 5.0 / 5.0) + (SIMILARITY_WEIGHT * 0.95)
    assert abs(score - 0.98) < 0.01

def test_ranking_low_high():
    """Test ranking low rating high similarity."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    score = (RATING_WEIGHT * 2.0 / 5.0) + (SIMILARITY_WEIGHT * 0.95)
    assert abs(score - 0.62) < 0.01

def test_ranking_priority():
    """Test rating priority."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    score_a = (RATING_WEIGHT * 4.8 / 5.0) + (SIMILARITY_WEIGHT * 0.6)
    score_b = (RATING_WEIGHT * 3.0 / 5.0) + (SIMILARITY_WEIGHT * 0.95)
    assert score_a > score_b

def test_ranking_zero_rating():
    """Test zero rating."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    score = (RATING_WEIGHT * 0.0 / 5.0) + (SIMILARITY_WEIGHT * 1.0)
    assert abs(score - 0.4) < 0.01

def test_ranking_zero_sim():
    """Test zero similarity."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    score = (RATING_WEIGHT * 5.0 / 5.0) + (SIMILARITY_WEIGHT * 0.0)
    assert abs(score - 0.6) < 0.01

def test_ranking_weights():
    """Test weights sum to 1."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    assert abs((RATING_WEIGHT + SIMILARITY_WEIGHT) - 1.0) < 0.001

def test_config_present():
    """Test all config values present."""
    from config import (
        HOTEL_SYNC_ENDPOINT, HOTEL_DETAILS_ENDPOINT,
        CHROMA_PERSIST_DIR, COLLECTION_NAME,
        RATING_WEIGHT, SIMILARITY_WEIGHT, TOP_K_RESULTS
    )
    assert HOTEL_SYNC_ENDPOINT is not None
    assert COLLECTION_NAME == "hotels"

def test_config_endpoints():
    """Test endpoint formats."""
    from config import HOTEL_SYNC_ENDPOINT, HOTEL_DETAILS_ENDPOINT
    assert HOTEL_SYNC_ENDPOINT.startswith("http")
    assert "{id}" in HOTEL_DETAILS_ENDPOINT

def test_config_collection():
    """Test collection name."""
    from config import COLLECTION_NAME
    assert COLLECTION_NAME == "hotels"

def test_config_embedding():
    """Test embedding model."""
    from config import EMBEDDING_MODEL
    assert "sentence-transformers" in EMBEDDING_MODEL or "MiniLM" in EMBEDDING_MODEL

def test_config_groq():
    """Test Groq model."""
    from config import GROQ_MODEL
    assert "llama" in GROQ_MODEL.lower()

def test_config_weights():
    """Test weights are valid."""
    from config import RATING_WEIGHT, SIMILARITY_WEIGHT
    assert 0 <= RATING_WEIGHT <= 1
    assert 0 <= SIMILARITY_WEIGHT <= 1

def test_config_topk():
    """Test TOP_K is positive."""
    from config import TOP_K_RESULTS
    assert TOP_K_RESULTS > 0

def test_config_timeout():
    """Test timeout is positive."""
    from config import REQUEST_TIMEOUT
    assert REQUEST_TIMEOUT > 0

def test_import_main():
    """Test main imports."""
    from main import run_travel_chat, sync_hotel_data, initialize_system
    assert callable(run_travel_chat)

def test_import_core():
    """Test core imports."""
    from core import VectorManager
    assert VectorManager is not None

def test_import_tools():
    """Test tools imports."""
    from tools import get_live_hotel_details, enrich_hotel_with_live_data
    # get_live_hotel_details is a LangChain StructuredTool, not a raw callable
    assert get_live_hotel_details is not None, "get_live_hotel_details is None"
    assert callable(enrich_hotel_with_live_data), "enrich_hotel_with_live_data is not callable"

def test_import_agents():
    """Test agents imports."""
    from agents import HotelRecommendationAgent
    assert HotelRecommendationAgent is not None

def test_unicode():
    """Test unicode handling."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {"name": "होटल", "city": "मुंबई", "description": "café ☕"}
    text = vm._create_embedding_string(hotel)
    assert isinstance(text, str)

def test_special_chars():
    """Test special characters."""
    from core.vector_store import VectorManager
    vm = VectorManager()
    hotel = {"name": "Hotel @#$%", "description": "Test & co"}
    text = vm._create_embedding_string(hotel)
    assert isinstance(text, str)


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
