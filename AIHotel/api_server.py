"""
AI Chat API Server

Uses Django's auth system for authentication.
Register/Login via Django (port 8000), then use the access token here.

Auth (Django - port 8000):
- POST /api/auth/register/  - Register new user
- POST /api/auth/login/     - Login and get JWT token

Chat (FastAPI - port 8001):
- POST /api/chat/send/                    - Send chat message (Bearer token required)
- GET  /api/chat/messages/?page=1&limit=10 - Get chat history (Bearer token required)
"""
import json
import logging
import os
import asyncio
from datetime import datetime
from typing import Optional, List

# Fix nested event loop issue (LangChain sync calls inside FastAPI async loop)
# Must set event loop policy BEFORE anything else creates a loop
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
import nest_asyncio
nest_asyncio.apply()

import asyncpg
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from jose import JWTError, jwt

from main import run_travel_chat, initialize_system

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =================================================================
# JWT Configuration - MUST match Django's SIMPLE_JWT SIGNING_KEY
# This is Django's SECRET_KEY used by djangorestframework-simplejwt
# =================================================================
DJANGO_SECRET_KEY = "django-insecure-j-j_r&1+&cr=u25)j4fpy!$m+@b*#hs-2rhv%1#m!i$!jq1#wf"
ALGORITHM = "HS256"

# HTTP Bearer token scheme
security = HTTPBearer()

# FastAPI app
app = FastAPI(
    title="AI Hotel Chat API",
    description=(
        "Chat API for hotel recommendations.\n\n"
        "**Authentication:** Use Django endpoints to get a token:\n"
        "- `POST http://localhost:8000/api/auth/register/` - Register\n"
        "- `POST http://localhost:8000/api/auth/login/` - Login\n\n"
        "Then use the `access` token as Bearer token here."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


# ============== Pydantic Models ==============

class ChatMessage(BaseModel):
    content: str


class ChatResponse(BaseModel):
    id: int
    user_message: str
    ai_response: str
    hotels: list
    created_at: str


class MessageListResponse(BaseModel):
    messages: List[ChatResponse]
    page: int
    limit: int
    total: int
    has_more: bool


# ============== Database Functions ==============

async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global db_pool

    if db_pool is None:
        db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "10.10.13.27"),
            port=int(os.getenv("DB_PORT", 5433)),
            database=os.getenv("DB_NAME", "hotel_db"),
            user=os.getenv("DB_USER", "hotel_user"),
            password=os.getenv("DB_PASSWORD", "hotel_pass"),
            min_size=5,
            max_size=20,
        )
        logger.info("Database pool created")

    return db_pool


async def init_chat_table():
    """Create chat_messages table if it doesn't exist."""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                hotels JSONB DEFAULT '[]',
                shown_hotel_ids JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
            )
        """)

        # Create index for faster queries
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id
            ON ai_chat_messages(user_id, created_at DESC)
        """)

        logger.info("Chat messages table initialized")


# ============== Auth - Validate Django JWT ==============

def verify_django_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token issued by Django Simple JWT.

    Django Simple JWT payload contains:
    {
        "token_type": "access",
        "exp": ...,
        "iat": ...,
        "jti": "...",
        "user_id": 42
    }
    """
    try:
        payload = jwt.decode(
            token,
            DJANGO_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True}
        )

        # Ensure it's an access token, not a refresh token
        if payload.get("token_type") != "access":
            logger.warning("Token is not an access token")
            return None

        return payload
    except JWTError as e:
        logger.error(f"Django token verification failed: {e}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to get current user from Django-issued JWT token.

    Returns dict with user_id and email (looked up from DB).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Get a token from Django: POST http://localhost:8000/api/auth/login/",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_django_token(credentials.credentials)

    if payload is None:
        raise credentials_exception

    user_id = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    # Look up user email from database
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email FROM auth_user WHERE id = $1 AND is_active = true",
            int(user_id),
        )

    if not user:
        raise credentials_exception

    return {"user_id": user["id"], "email": user["email"]}


# ============== API Endpoints ==============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting AI Chat API Server...")

    # Initialize database pool
    await get_db_pool()

    # Initialize chat table
    await init_chat_table()

    # Initialize AI system
    await initialize_system()

    logger.info("AI Chat API Server ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "AI Hotel Chat API",
        "auth": "Use Django endpoints for register/login (port 8000)",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.get("/swagger")
@app.get("/swagger/")
async def swagger_redirect():
    """Redirect to Swagger docs."""
    return RedirectResponse(url="/docs")


# ============== Chat Endpoints ==============

@app.post("/api/chat/send/", response_model=ChatResponse)
async def send_chat_message(
    message: ChatMessage,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a chat message and get AI response.

    **Authentication:** Bearer token from Django login required.

    Request body:
    ```json
    {
        "content": "find me hotel in Melbourne with pool"
    }
    ```
    """
    user_id = current_user["user_id"]

    pool = await get_db_pool()

    # Get recent conversation history for context
    async with pool.acquire() as conn:
        recent_messages = await conn.fetch("""
            SELECT user_message, ai_response, shown_hotel_ids
            FROM ai_chat_messages
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 5
        """, user_id)

    # Build conversation history
    history = []
    shown_hotel_ids = []

    for msg in reversed(recent_messages):
        history.append({"role": "user", "content": msg["user_message"]})
        history.append({"role": "assistant", "content": msg["ai_response"]})
        # Parse shown_hotel_ids - may be JSON string, list, or None
        raw_ids = msg["shown_hotel_ids"]
        if raw_ids:
            if isinstance(raw_ids, str):
                try:
                    parsed = json.loads(raw_ids)
                    if isinstance(parsed, list):
                        shown_hotel_ids.extend([int(x) for x in parsed if x is not None])
                except (json.JSONDecodeError, ValueError):
                    pass
            elif isinstance(raw_ids, list):
                shown_hotel_ids.extend([int(x) for x in raw_ids if x is not None])

    # Deduplicate and ensure all are integers
    shown_hotel_ids = list(set(shown_hotel_ids))

    # Get AI response
    result = await run_travel_chat(
        query=message.content,
        history=history,
        shown_hotel_ids=shown_hotel_ids,
    )

    ai_response = result.get("natural_language_response", "")
    hotels = result.get("recommended_hotels", [])
    new_shown_ids = result.get("shown_hotel_ids", [])

    # Ensure shown_hotel_ids are integers
    clean_shown_ids = []
    for sid in new_shown_ids:
        try:
            clean_shown_ids.append(int(sid))
        except (ValueError, TypeError):
            pass

    # Save to database
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO ai_chat_messages (
                user_id,
                user_message,
                ai_response,
                hotels,
                shown_hotel_ids,
                created_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)
            RETURNING id, created_at
        """,
            user_id,
            message.content,
            ai_response,
            json.dumps(hotels),
            json.dumps(clean_shown_ids),
            datetime.utcnow(),
        )

    logger.info(f"Chat message saved for user {user_id}, message_id: {row['id']}")

    return ChatResponse(
        id=row["id"],
        user_message=message.content,
        ai_response=ai_response,
        hotels=hotels,
        created_at=row["created_at"].isoformat(),
    )


@app.get("/api/chat/messages/", response_model=MessageListResponse)
async def get_chat_messages(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Messages per page"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get chat message history with pagination.

    **Authentication:** Bearer token from Django login required.

    Query params:
    - **page**: Page number (default: 1)
    - **limit**: Messages per page (default: 10, max: 50)

    Examples:
    - `GET /api/chat/messages/?page=1&limit=10` → Latest 10 messages
    - `GET /api/chat/messages/?page=2&limit=10` → Previous 10 messages
    """
    user_id = current_user["user_id"]
    offset = (page - 1) * limit

    pool = await get_db_pool()

    async with pool.acquire() as conn:
        # Get total count
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM ai_chat_messages WHERE user_id = $1",
            user_id,
        )

        # Get messages with pagination (newest first)
        rows = await conn.fetch("""
            SELECT id, user_message, ai_response, hotels, created_at
            FROM ai_chat_messages
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)

    messages = []
    for row in rows:
        hotels_raw = row["hotels"]
        if isinstance(hotels_raw, str):
            hotels = json.loads(hotels_raw) if hotels_raw else []
        elif hotels_raw is None:
            hotels = []
        else:
            hotels = hotels_raw
        messages.append(ChatResponse(
            id=row["id"],
            user_message=row["user_message"],
            ai_response=row["ai_response"],
            hotels=hotels,
            created_at=row["created_at"].isoformat(),
        ))

    has_more = (offset + len(messages)) < total

    return MessageListResponse(
        messages=messages,
        page=page,
        limit=limit,
        total=total,
        has_more=has_more,
    )


# ============== Run Server ==============

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
        timeout_keep_alive=120,
        loop="asyncio",
    )
