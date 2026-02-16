"""
Configuration settings for the Hotel Recommendation Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Endpoints
HOTEL_SYNC_ENDPOINT = "http://10.10.13.27:8000/api/hotel/sync/"
HOTEL_DETAILS_ENDPOINT = "http://10.10.13.27:8000/api/hotel/ai/details/{id}/"

# LLM Configuration
# Primary: OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")  # or gpt-4o, gpt-3.5-turbo

# Fallback: Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Vector Store Configuration
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
COLLECTION_NAME = "hotels"

# Embedding Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Ranking Configuration
RATING_WEIGHT = 0.6
SIMILARITY_WEIGHT = 0.4
TOP_K_RESULTS = 5

# Request Configuration
REQUEST_TIMEOUT = 30
