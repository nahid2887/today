# 🔌 API Integration Guide for Django Developers
## Converting AI Hotel Chatbot to REST APIs

**Target Audience:** Django Backend Developers  
**Current System:** LangGraph-based chatbot in `main.py`  
**Goal:** Create REST APIs to expose chatbot functionality  
**Date:** February 10, 2026

---

## 📋 Table of Contents
1. [Understanding the Current System](#understanding-the-current-system)
2. [Django REST Framework Setup](#django-rest-framework-setup)
3. [API Endpoints Design](#api-endpoints-design)
4. [Implementation Examples](#implementation-examples)
5. [Request/Response Formats](#requestresponse-formats)
6. [Deployment Guide](#deployment-guide)

---

## 🚀 Quick Overview: Using main.py in Django

### The Magic Function: `run_travel_chat()`

The entire chatbot functionality is wrapped in **one async function** in `main.py`:

```python
# From main.py
async def run_travel_chat(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    shown_hotel_ids: Optional[List[int]] = None,
    last_hotels: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
```

**What it does:**
- Takes a natural language query (e.g., "hotels in Miami")
- Maintains conversation context through `history`
- Avoids showing duplicate hotels using `shown_hotel_ids`
- Returns formatted response with hotels and metadata

**How to call it from Django:**
```python
import asyncio
from main import run_travel_chat

# Method 1: In async Django view (Django 3.1+)
async def async_chat_view(request):
    result = await run_travel_chat("hotels in Miami")
    return JsonResponse(result)

# Method 2: In regular Django view (most common)
def chat_view(request):
    result = asyncio.run(run_travel_chat("hotels in Miami"))
    return JsonResponse(result)
```

**That's it!** The rest of this guide shows you how to wrap this properly in REST APIs with session management, error handling, and production features.

---

## 🏗️ Understanding the Current System

### Current Architecture
```
main.py
├── Hotel Agent (LangGraph)
│   ├── OpenAI LLM (primary)
│   ├── Groq LLM (fallback)
│   ├── PostgreSQL Database
│   └── Vector Search (sentence-transformers)
│
└── Orchestrator
    ├── Query Classification
    ├── Filter Extraction
    ├── Hotel Search
    └── Response Generation
```

### Key Components in `main.py`

#### 1. **Graph Initialization** (Lines 1-50)
```python
from agents.orchestrator import build_orchestrator_graph

# This builds the entire chatbot system
graph = build_orchestrator_graph()
```

#### 2. **Main Chat Function** (from main.py)
```python
async def run_travel_chat(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    shown_hotel_ids: Optional[List[int]] = None,
    last_hotels: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main entry point for the travel assistant chatbot.
    
    Args:
        query: User's natural language query (e.g., "hotels in Miami under $200")
        history: Conversation history for context (optional)
        shown_hotel_ids: List of hotel IDs already shown to avoid duplicates (optional)
        last_hotels: Previous search results for refinement queries (optional)
    
    Returns:
        {
            "natural_language_response": "Here are 3 hotels in Miami...",
            "recommended_hotels": [{...}, {...}, {...}],
            "shown_hotel_ids": [1, 2, 3],
            "last_hotels": [...],
            "metadata": {
                "query": "hotels in Miami under $200",
                "query_type": "hotel_search",
                "filters_applied": {"city": "Miami", "max_price": 200},
                "total_found": 3,
                "total_shown_in_session": 3
            }
        }
    """
```

**Important Notes:**
1. This is an **async function** - must be called with `await` or `asyncio.run()`
2. The system auto-initializes on first call
3. Pass `history` for multi-turn conversations
4. Pass `shown_hotel_ids` to avoid showing duplicates in same session

#### 3. **Dependencies**
```python
# Core dependencies (from pyproject.toml)
- langchain-openai    # OpenAI integration
- langchain-groq      # Groq integration  
- langgraph           # Workflow orchestration
- asyncpg             # PostgreSQL async driver
- sentence-transformers # Vector search
```

---

## 🛠️ Django REST Framework Setup

### Step 1: Install Dependencies

Create a new Django project or add to existing:

```bash
# Install Django REST Framework
pip install djangorestframework
pip install django-cors-headers  # For frontend CORS

# Install chatbot dependencies
pip install langchain-openai langchain-groq langgraph
pip install asyncpg sentence-transformers
```

### Step 2: Project Structure

```
your_django_project/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── chatbot_api/          # New Django app
│   ├── __init__.py
│   ├── views.py          # API views
│   ├── serializers.py    # Request/response schemas
│   ├── urls.py           # API routes
│   ├── services.py       # Chatbot integration
│   └── models.py         # (optional) conversation history
└── aihotel/              # Copy from original project
    ├── agents/
    ├── core/
    ├── config/
    └── main.py
```

### Step 3: Django Settings Configuration

Add to `config/settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'corsheaders',
    
    # Your apps
    'chatbot_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings (for frontend)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React
    "http://localhost:8080",  # Vue
    "http://localhost:4200",  # Angular
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    }
}

# Environment variables (copy from AIHotel/.env)
import os
from pathlib import Path

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# PostgreSQL settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME", "hotel_db"),
        'USER': os.getenv("DB_USER", "postgres"),
        'PASSWORD': os.getenv("DB_PASSWORD", "password"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "5432"),
    }
}
```

---

## 🎯 API Endpoints Design

### Recommended API Structure

```
POST   /api/v1/chat/query/              # Main chatbot endpoint
GET    /api/v1/chat/health/             # Health check
POST   /api/v1/hotels/search/           # Direct hotel search (no LLM)
GET    /api/v1/hotels/{id}/             # Get hotel details
GET    /api/v1/hotels/cities/           # List available cities
GET    /api/v1/hotels/amenities/        # List available amenities
POST   /api/v1/chat/sessions/           # Create chat session
GET    /api/v1/chat/sessions/{id}/      # Get session history
DELETE /api/v1/chat/sessions/{id}/      # Clear session
```

### Endpoint Details

#### 1. **POST /api/v1/chat/query/** (Main Endpoint)
```json
Request:
{
  "query": "hotels in Miami under $200 with pool",
  "session_id": "user-123-session",
  "reset_session": false
}

Response:
{
  "status": "success",
  "query": "hotels in Miami under $200 with pool",
  "query_type": "hotel_search",
  "response": "I found 3 amazing hotels in Miami under $200 with a pool! The Sunset Beach Resort (4.5/10) is a great option at $189/night...",
  "hotels": [
    {
      "id": 1,
      "hotel_name": "Sunset Beach Resort",
      "city": "Miami",
      "country": "USA",
      "average_rating": 4.5,
      "total_ratings": 498,
      "base_price_per_night": 189.0,
      "amenities": ["Pool", "Free Wi-Fi", "Spa"],
      "images": ["https://example.com/image1.jpg"],
      "description": "Beautiful beachfront resort with ocean views...",
      "similarity_score": 0.823,
      "composite_score": 0.756,
      "match_reason": "Excellent match for your request (82% relevance)",
      "badges": ["15% OFF"],
      "perks": ["Free breakfast", "Late checkout"]
    }
  ],
  "filters": {
    "city": "Miami",
    "max_price": 200,
    "amenities": ["Pool"]
  },
  "total_found": 3,
  "total_shown_in_session": 3,
  "processing_time": 2.8,
  "session_id": "user-123-session",
  "timestamp": "2026-02-10T10:30:00Z"
}

Error Response (400 Bad Request):
{
  "status": "error",
  "error": "Invalid query format",
  "message": "Query cannot be empty"
}

Error Response (429 Too Many Requests):
{
  "status": "error",
  "error": "Rate limit exceeded",
  "message": "Try again in 60 seconds"
}

Error Response (500 Internal Server Error):
{
  "status": "error",
  "error": "Processing failed",
  "message": "LLM service unavailable",
  "fallback_used": true
}
```

#### 2. **GET /api/v1/chat/health/**
```json
Response:
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "openai": "available",
    "groq": "available",
    "vector_search": "loaded"
  },
  "version": "1.0.0",
  "timestamp": "2026-02-10T10:30:00Z"
}
```

#### 3. **POST /api/v1/hotels/search/** (Direct Search - No LLM)
```json
Request:
{
  "city": "Miami",
  "min_rating": 4.0,
  "max_price": 200,
  "amenities": ["Pool", "WiFi"],
  "limit": 10
}

Response:
{
  "status": "success",
  "count": 1,
  "hotels": [...]
}
```

---

## 💻 Implementation Examples

### 1. Create Serializers (`chatbot_api/serializers.py`)

```python
from rest_framework import serializers

class ChatQuerySerializer(serializers.Serializer):
    """Input validation for chat queries"""
    query = serializers.CharField(
        max_length=500,
        min_length=1,
        required=True,
        help_text="User's natural language query (e.g., 'hotels in Miami under $200')"
    )
    session_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional session ID for multi-turn conversations (any string)"
    )
    reset_session = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Set to true to clear session history before this query"
    )

class HotelSerializer(serializers.Serializer):
    """Hotel data structure"""
    hotel_id = serializers.IntegerField()
    hotel_name = serializers.CharField()
    city = serializers.CharField()
    rating = serializers.FloatField()
    reviews_count = serializers.IntegerField()
    price = serializers.CharField()
    amenities = serializers.ListField(child=serializers.CharField())
    description = serializers.CharField()
    similarity_score = serializers.FloatField(required=False)

class ChatResponseSerializer(serializers.Serializer):
    """Chatbot response structure"""
    status = serializers.CharField()
    query_type = serializers.CharField()
    response = serializers.CharField()
    hotels = HotelSerializer(many=True, required=False)
    filters = serializers.DictField(required=False)
    processing_time = serializers.FloatField()
    timestamp = serializers.DateTimeField()

class ErrorResponseSerializer(serializers.Serializer):
    """Error response structure"""
    status = serializers.CharField(default="error")
    error = serializers.CharField()
    message = serializers.CharField()
    fallback_used = serializers.BooleanField(required=False)
```

### 2. Create Chatbot Service (`chatbot_api/services.py`)

**This is the most important file - it connects Django to main.py**

```python
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the AIHotel directory to Python path
aihotel_path = Path(__file__).parent.parent / 'aihotel'
sys.path.insert(0, str(aihotel_path))

# Import the main chatbot function
from main import run_travel_chat, initialize_system, get_database_statistics

class ChatbotService:
    """
    Service class to interact with the AI Hotel chatbot
    Wraps main.py's run_travel_chat function for Django
    """
    
    _instance = None
    _initialized = False
    _sessions = {}  # Store session state: {session_id: {history, shown_hotel_ids, last_hotels}}
    
    def __new__(cls):
        """Singleton pattern to reuse instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def _ensure_initialized(self):
        """Ensure the chatbot system is initialized"""
        if not self._initialized:
            await initialize_system()
            self._initialized = True
    
    def _get_session_state(self, session_id: Optional[str]) -> Dict[str, Any]:
        """Get or create session state"""
        if not session_id:
            return {
                "history": [],
                "shown_hotel_ids": [],
                "last_hotels": []
            }
        
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "history": [],
                "shown_hotel_ids": [],
                "last_hotels": []
            }
        
        return self._sessions[session_id]
    
    def _update_session_state(self, session_id: Optional[str], query: str, result: Dict[str, Any]):
        """Update session state after query"""
        if not session_id:
            return
        
        state = self._sessions[session_id]
        
        # Update history
        state["history"].append({"role": "user", "content": query})
        state["history"].append({"role": "assistant", "content": result["natural_language_response"]})
        
        # Keep only last 10 messages (5 turns)
        if len(state["history"]) > 10:
            state["history"] = state["history"][-10:]
        
        # Update shown hotel IDs
        state["shown_hotel_ids"] = result.get("shown_hotel_ids", [])
        
        # Update last hotels
        state["last_hotels"] = result.get("last_hotels", [])
    
    async def process_query_async(
        self, 
        query: str, 
        session_id: Optional[str] = None,
        reset_session: bool = False
    ) -> Dict[str, Any]:
        """
        Process a user query through the chatbot using main.py's run_travel_chat
        
        Args:
            query: User's natural language query
            session_id: Optional session ID for multi-turn conversations
            reset_session: If True, clear session history before processing
        
        Returns:
            Dictionary with response and results
        """
        try:
            # Ensure system is initialized
            await self._ensure_initialized()
            
            # Reset session if requested
            if reset_session and session_id and session_id in self._sessions:
                del self._sessions[session_id]
            
            # Get session state
            state = self._get_session_state(session_id)
            
            # Record start time
            start_time = datetime.now()
            
            # Call the main chatbot function from main.py
            result = await run_travel_chat(
                query=query,
                history=state["history"],
                shown_hotel_ids=state["shown_hotel_ids"],
                last_hotels=state["last_hotels"]
            )
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Update session state
            self._update_session_state(session_id, query, result)
            
            # Format response for API
            response_data = {
                "status": "success",
                "query": query,
                "query_type": result.get("metadata", {}).get("query_type", "unknown"),
                "response": result.get("natural_language_response", ""),
                "hotels": result.get("recommended_hotels", []),
                "filters": result.get("metadata", {}).get("filters_applied", {}),
                "total_found": result.get("metadata", {}).get("total_found", 0),
                "total_shown_in_session": result.get("metadata", {}).get("total_shown_in_session", 0),
                "processing_time": processing_time,
                "session_id": session_id,
                "timestamp": end_time.isoformat()
            }
            
            return response_data
            
        except Exception as e:
            return {
                "status": "error",
                "error": "processing_failed",
                "message": str(e),
                "query": query,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
    
    def process_query(
        self, 
        query: str, 
        session_id: Optional[str] = None,
        reset_session: bool = False
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for async process_query_async
        Django views can call this directly from regular (non-async) views
        """
        return asyncio.run(self.process_query_async(query, session_id, reset_session))
    
    async def health_check_async(self) -> Dict[str, Any]:
        """Check if all services are available"""
        try:
            await self._ensure_initialized()
            
            # Get database statistics
            stats = await get_database_statistics()
            
            return {
                "status": "healthy",
                "services": {
                    "database": "connected",
                    "llm": "available",
                    "vector_search": "loaded"
                },
                "database_stats": {
                    "total_hotels": stats.get("total_hotels", 0),
                    "total_cities": stats.get("total_cities", 0),
                    "price_range": f"${stats.get('min_price', 0):.0f} - ${stats.get('max_price', 0):.0f}"
                },
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Synchronous wrapper for health check"""
        return asyncio.run(self.health_check_async())
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a specific session's data"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session"""
        if session_id not in self._sessions:
            return None
        
        state = self._sessions[session_id]
        return {
            "session_id": session_id,
            "message_count": len(state["history"]),
            "hotels_shown": len(state["shown_hotel_ids"]),
            "last_query": state["history"][-2]["content"] if len(state["history"]) >= 2 else None
        }
```

**Key Points:**

1. **Direct Integration**: Imports `run_travel_chat` directly from `main.py`
2. **Session Management**: Automatically tracks conversation history and shown hotels
3. **Async Handling**: Provides both async and sync methods for flexibility
4. **Error Handling**: Comprehensive try-catch with detailed error messages
5. **Singleton Pattern**: Single instance shared across all requests

### 3. Create API Views (`chatbot_api/views.py`)

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    ChatQuerySerializer,
    ChatResponseSerializer,
    ErrorResponseSerializer
)
from .services import ChatbotService

class ChatQueryView(APIView):
    """
    Main chatbot endpoint
    Processes natural language queries and returns hotel recommendations
    """
    permission_classes = [AllowAny]  # Change to IsAuthenticated for production
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    
    @swagger_auto_schema(
        operation_description="Process a natural language query",
        request_body=ChatQuerySerializer,
        responses={
            200: ChatResponseSerializer,
            400: ErrorResponseSerializer,
            429: "Rate limit exceeded",
            500: ErrorResponseSerializer
        }
    )
    def post(self, request):
        """Process chatbot query"""
        # Validate input
        serializer = ChatQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "error": "validation_failed",
                    "message": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract data
        query = serializer.validated_data['query']
        session_id = serializer.validated_data.get('session_id')
        reset_session = serializer.validated_data.get('reset_session', False)
        
        # Process query using main.py's run_travel_chat function
        chatbot = ChatbotService()
        result = chatbot.process_query(query, session_id, reset_session)
        
        # Return response
        if result.get('status') == 'error':
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(result, status=status.HTTP_200_OK)


class HealthCheckView(APIView):
    """
    Health check endpoint
    Returns status of all services
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Check API and services health",
        responses={
            200: openapi.Response(
                description="Service status",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'services': openapi.Schema(type=openapi.TYPE_OBJECT),
                        'version': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        }
    )
    def get(self, request):
        """Get health status"""
        chatbot = ChatbotService()
        result = chatbot.health_check()
        
        response_status = (
            status.HTTP_200_OK 
            if result.get('status') == 'healthy' 
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
        return Response(result, status=response_status)


class DirectHotelSearchView(APIView):
    """
    Direct hotel search without LLM
    Faster for structured queries
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Search hotels with structured filters"""
        # This would call the database directly
        # bypassing the LLM for faster results
        
        filters = {
            'city': request.data.get('city'),
            'min_rating': request.data.get('min_rating'),
            'max_price': request.data.get('max_price'),
            'amenities': request.data.get('amenities', []),
            'limit': request.data.get('limit', 10)
        }
        
        # TODO: Implement direct database query
        # from core.integrated_search import IntegratedSearch
        # search = IntegratedSearch()
        # results = await search.search_hotels(filters)
        
        return Response({
            "status": "success",
            "count": 0,
            "hotels": [],
            "message": "Direct search - implement database query"
        })
```

### 4. Create URL Routes (`chatbot_api/urls.py`)

```python
from django.urls import path
from .views import ChatQueryView, HealthCheckView, DirectHotelSearchView

app_name = 'chatbot_api'

urlpatterns = [
    # Main endpoints
    path('query/', ChatQueryView.as_view(), name='chat-query'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('search/', DirectHotelSearchView.as_view(), name='direct-search'),
]
```

### 5. Include in Main URLs (`config/urls.py`)

```python
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Swagger documentation
schema_view = get_schema_view(
   openapi.Info(
      title="AI Hotel Chatbot API",
      default_version='v1',
      description="REST API for AI-powered hotel recommendations",
      terms_of_service="https://www.example.com/terms/",
      contact=openapi.Contact(email="api@aihotel.com"),
      license=openapi.License(name="MIT License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/v1/chat/', include('chatbot_api.urls')),
    
    # API documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='api-redoc'),
]
```

---

## ⚡ Quick Start Guide

### Complete Example in 5 Steps

**Step 1: Copy AIHotel folder to Django project**
```bash
cd your_django_project/
cp -r /path/to/AIHotel ./aihotel
```

**Step 2: Create chatbot_api app**
```bash
python manage.py startapp chatbot_api
```

**Step 3: Create services.py** (copy the ChatbotService class from above)
```bash
# Copy the entire ChatbotService class to:
# chatbot_api/services.py
```

**Step 4: Create views.py**
```python
# chatbot_api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import ChatbotService

class ChatQueryView(APIView):
    def post(self, request):
        query = request.data.get('query')
        session_id = request.data.get('session_id')
        
        if not query:
            return Response(
                {"status": "error", "message": "Query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        chatbot = ChatbotService()
        result = chatbot.process_query(query, session_id)
        
        return Response(result, status=status.HTTP_200_OK)

class HealthCheckView(APIView):
    def get(self, request):
        chatbot = ChatbotService()
        result = chatbot.health_check()
        return Response(result, status=status.HTTP_200_OK)
```

**Step 5: Add URLs and test**
```python
# chatbot_api/urls.py
from django.urls import path
from .views import ChatQueryView, HealthCheckView

urlpatterns = [
    path('query/', ChatQueryView.as_view()),
    path('health/', HealthCheckView.as_view()),
]

# config/urls.py
urlpatterns = [
    path('api/v1/chat/', include('chatbot_api.urls')),
]
```

**Test It:**
```bash
# Start Django server
python manage.py runserver

# Test health check
curl http://localhost:8000/api/v1/chat/health/

# Test query
curl -X POST http://localhost:8000/api/v1/chat/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "hotels in Miami under $200"}'
```

---

## 📡 Request/Response Formats

### Frontend Integration Examples

#### JavaScript/Axios Example
```javascript
// Install: npm install axios

import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

async function searchHotels(query) {
  try {
    const response = await axios.post(`${API_BASE_URL}/chat/query/`, {
      query: query,
      session_id: localStorage.getItem('sessionId') || null
    });
    
    console.log('Response:', response.data.response);
    console.log('Hotels:', response.data.hotels);
    
    return response.data;
    
  } catch (error) {
    if (error.response) {
      // Server responded with error
      console.error('Error:', error.response.data.message);
    } else {
      // Network error
      console.error('Network error:', error.message);
    }
    throw error;
  }
}

// Usage
searchHotels("hotels in Miami under $200")
  .then(data => {
    // Update UI with results
    displayHotels(data.hotels);
  })
  .catch(error => {
    // Show error message
    showError(error);
  });
```

#### Python/Requests Example
```python
# Install: pip install requests

import requests

API_BASE_URL = 'http://localhost:8000/api/v1'

def search_hotels(query, session_id=None):
    """Search hotels using the chatbot API"""
    
    url = f"{API_BASE_URL}/chat/query/"
    payload = {
        "query": query,
        "session_id": session_id
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"Response: {data['response']}")
        print(f"Found {len(data.get('hotels', []))} hotels")
        
        return data
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.json()}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise

# Usage
result = search_hotels("hotels in Miami under $200")
for hotel in result.get('hotels', []):
    print(f"- {hotel['hotel_name']} ({hotel['rating']}/5)")
```

#### cURL Example
```bash
# Test the API from command line

# 1. Health check
curl -X GET http://localhost:8000/api/v1/chat/health/

# 2. Search hotels
curl -X POST http://localhost:8000/api/v1/chat/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "hotels in Miami under $200 with pool"
  }'

# 3. With authentication (if enabled)
curl -X POST http://localhost:8000/api/v1/chat/query/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your-auth-token-here" \
  -d '{
    "query": "hotels in Miami"
  }'
```

---

## 🚀 Deployment Guide

### Step 1: Environment Setup

Create `.env` file in Django project root:
```bash
# Django settings
SECRET_KEY=your-django-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.yourhotel.com,localhost

# Database
DB_NAME=hotel_db
DB_USER=postgres
DB_PASSWORD=your-password-here
DB_HOST=localhost
DB_PORT=5432

# LLM APIs
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...

# CORS
CORS_ALLOWED_ORIGINS=https://yourfrontend.com,http://localhost:3000
```

### Step 2: Database Migration

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Step 3: Run Development Server

```bash
# Start Django development server
python manage.py runserver 0.0.0.0:8000

# Access API documentation
# http://localhost:8000/api/docs/
```

### Step 4: Production Deployment

#### Option A: Gunicorn + Nginx
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile access.log \
  --error-logfile error.log
```

#### Option B: Docker
```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run Gunicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=db
      - DB_NAME=hotel_db
      - DB_USER=postgres
      - DB_PASSWORD=password
    depends_on:
      - db
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=hotel_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## 🔒 Security Considerations

### 1. Authentication
```python
# Add JWT authentication
pip install djangorestframework-simplejwt

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}
```

### 2. Rate Limiting
```python
# Already configured in REST_FRAMEWORK settings
'DEFAULT_THROTTLE_RATES': {
    'anon': '100/day',
    'user': '1000/day'
}
```

### 3. Input Validation
```python
# Always validate and sanitize user input
class ChatQuerySerializer(serializers.Serializer):
    query = serializers.CharField(
        max_length=500,  # Limit length
        trim_whitespace=True,
        validators=[no_sql_injection_validator]
    )
```

### 4. HTTPS Only
```python
# settings.py (production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## 📊 Monitoring & Logging

### Add Logging
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'chatbot_api.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'chatbot_api': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Usage in Views
```python
import logging

logger = logging.getLogger('chatbot_api')

class ChatQueryView(APIView):
    def post(self, request):
        logger.info(f"Query received: {request.data.get('query')}")
        # ... process query ...
        logger.info(f"Query processed in {processing_time}s")
```

---

## 🧪 Testing

### Unit Tests (`chatbot_api/tests.py`)
```python
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

class ChatbotAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/api/v1/chat/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
    
    def test_query_endpoint(self):
        """Test chat query endpoint"""
        response = self.client.post(
            '/api/v1/chat/query/',
            {'query': 'hotels in Miami'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('response', response.data)
        self.assertIn('hotels', response.data)
    
    def test_invalid_query(self):
        """Test with invalid query"""
        response = self.client.post(
            '/api/v1/chat/query/',
            {'query': ''},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

# Run tests
# python manage.py test chatbot_api
```

---

## 📝 Summary Checklist

### For Django Developer:

- [ ] Install Django REST Framework and dependencies
- [ ] Create `chatbot_api` Django app
- [ ] Copy `aihotel/` folder to Django project
- [ ] Configure settings.py (CORS, REST_FRAMEWORK, etc.)
- [ ] Create serializers for request/response validation
- [ ] Create ChatbotService to wrap main.py functionality
- [ ] Create API views (ChatQueryView, HealthCheckView)
- [ ] Configure URL routing
- [ ] Set up environment variables (.env)
- [ ] Test locally with cURL or Postman
- [ ] Add authentication if needed
- [ ] Deploy with Gunicorn + Nginx or Docker
- [ ] Set up monitoring and logging
- [ ] Write unit tests

### Key Files to Create:
1. `chatbot_api/services.py` - Chatbot integration
2. `chatbot_api/serializers.py` - Request/response schemas
3. `chatbot_api/views.py` - API endpoints
4. `chatbot_api/urls.py` - URL routing
5. `config/settings.py` - Django configuration

### Testing URLs:
- Health: `http://localhost:8000/api/v1/chat/health/`
- Query: `http://localhost:8000/api/v1/chat/query/`
- Docs: `http://localhost:8000/api/docs/`

---

## 🎯 Next Steps

1. **Start with health check** - Test `/api/v1/chat/health/` first
2. **Test simple query** - Try "hotels in Miami"
3. **Add authentication** - Implement JWT tokens
4. **Deploy to staging** - Test in production-like environment
5. **Frontend integration** - Connect to React/Vue/Angular app
6. **Monitor performance** - Track response times and errors
7. **Scale as needed** - Add load balancer, cache layer, etc.

---

## 💬 Support

For questions or issues:
- Check Django REST Framework docs: https://www.django-rest-framework.org/
- Review LangGraph docs: https://python.langchain.com/docs/langgraph
- Test with API docs: http://localhost:8000/api/docs/

**Good luck with your API integration!** 🚀
