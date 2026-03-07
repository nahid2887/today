"""
Configuration settings for the Hotel Recommendation Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Endpoints (legacy - sync is obsolete, system uses direct DB queries)
HOTEL_SYNC_ENDPOINT = os.getenv("HOTEL_SYNC_ENDPOINT", "https://app.tri2directaitravel.com.au/api/hotel/sync/")
HOTEL_DETAILS_ENDPOINT = os.getenv("HOTEL_DETAILS_ENDPOINT", "https://app.tri2directaitravel.com.au/api/hotel/ai/details/{id}/")

# LLM Configuration (Groq)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Fast/cheap model for classify, city extraction, query correction, Tavily JSON parsing.
# Free plan: llama-3.1-8b-instant has 500K TPD vs 100K for the 70B model.
# Switch all non-response-generation calls here to preserve the 70B quota for quality replies.
GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")

# Tavily Web Search (external hotel fallback)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# Vector Store Configuration
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
COLLECTION_NAME = "hotels"

# Embedding Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Ranking Configuration
RATING_WEIGHT = 0.8
SIMILARITY_WEIGHT = 0.2
TOP_K_RESULTS = 5

# Request Configuration
REQUEST_TIMEOUT = 30
