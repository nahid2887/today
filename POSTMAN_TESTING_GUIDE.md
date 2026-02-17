# AI Chat API - Postman Testing Guide

## 🚀 Quick Setup

### 1. Import Collection
- Open Postman
- Click **Import** 
- Select `AI_Chat_Postman_Collection.json`
- Collection will be imported with all endpoints

### 2. Test Authentication
**Step 1: Register User**
```
POST http://localhost:8000/api/auth/register/
{
  "username": "chatuser",
  "email": "chatuser@example.com", 
  "password": "testpass123",
  "user_type": "traveler"
}
```

**Step 2: Login User**
```
POST http://localhost:8000/api/auth/login/
{
  "username": "chatuser",
  "password": "testpass123"
}
```
→ Copy the `access` token from response

### 3. Set Authorization
- Go to Collection Settings → Authorization
- Select "Bearer Token"
- Paste your JWT token in the Token field

## 🧪 Test Flow

### Test 1: Create Chat Session
```
POST http://localhost:8000/api/chat/sessions/
{
  "title": "Hotel Search Chat"
}
```

**Expected Response:**
```json
{
  "id": 1,
  "title": "Hotel Search Chat",
  "status": "active",
  "metadata": {},
  "shown_hotel_ids": [],
  "last_hotels": [],
  "messages": [],
  "message_count": 0,
  "created_at": "2026-02-16T...",
  "updated_at": "2026-02-16T..."
}
```

### Test 2: Send Message
```
POST http://localhost:8000/api/chat/sessions/1/send/
{
  "content": "I need a hotel in Sydney with a pool"
}
```

**Expected Response:**
```json
{
  "user_message_id": 1,
  "assistant_message_id": 2, 
  "session_id": 1,
  "status": "processing"
}
```

### Test 3: Get Messages
```
GET http://localhost:8000/api/chat/sessions/1/messages/
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "role": "user",
    "content": "I need a hotel in Sydney with a pool",
    "is_streaming": false,
    "is_complete": true,
    "recommended_hotels": [],
    "created_at": "2026-02-16T..."
  },
  {
    "id": 2, 
    "role": "assistant",
    "content": "Great choice! I've found some excellent hotels in Sydney with pools...",
    "is_streaming": false,
    "is_complete": true,
    "recommended_hotels": [...],
    "created_at": "2026-02-16T..."
  }
]
```

### Test 4: Stream Response (Browser Test)
Since Postman doesn't handle Server-Sent Events well, test streaming in browser:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chat Stream Test</title>
</head>
<body>
    <div id="response"></div>
    <script>
        const token = 'YOUR_JWT_TOKEN_HERE';
        const eventSource = new EventSource(
            'http://localhost:8000/api/chat/sessions/1/messages/2/stream/', 
            { headers: { 'Authorization': `Bearer ${token}` } }
        );
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('Chunk:', data);
            
            if (data.chunk) {
                document.getElementById('response').innerHTML += data.chunk;
            }
            
            if (data.is_complete) {
                console.log('Hotels:', data.recommended_hotels);
                eventSource.close();
            }
        };
    </script>
</body>
</html>
```

## 📋 All Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/chat/sessions/` | List all chat sessions |
| `POST` | `/api/chat/sessions/` | Create new chat session |
| `GET` | `/api/chat/sessions/{id}/` | Get session details |
| `PUT` | `/api/chat/sessions/{id}/` | Update session |
| `DELETE` | `/api/chat/sessions/{id}/` | Archive session |
| `GET` | `/api/chat/sessions/{id}/messages/` | List messages |
| `POST` | `/api/chat/sessions/{id}/send/` | Send message |
| `GET` | `/api/chat/sessions/{id}/messages/{msg_id}/stream/` | Stream AI response |
| `POST` | `/api/chat/messages/{msg_id}/hotels/{hotel_id}/clicked/` | Mark hotel clicked |
| `POST` | `/api/chat/messages/{msg_id}/hotels/{hotel_id}/booked/` | Mark hotel booked |

## 🔍 Expected AI Response Format

When you send a message like "I need a hotel in Sydney with a pool", the AI will respond with:

```json
{
  "chunk": "",
  "is_complete": true,
  "recommended_hotels": [
    {
      "id": 34,
      "hotel_name": "Hyatt Regency Sydney",
      "city": "Sydney", 
      "country": "Australia",
      "base_price_per_night": 350.0,
      "average_rating": 8.3,
      "amenities": ["Pool", "Free Wi-Fi"],
      "images": ["http://localhost:8000/media/hotel_images/..."],
      "relevance_score": 0.95,
      "match_reason": "Pool amenity • Excellent 8.3 star rating • Located in Sydney"
    }
  ],
  "metadata": {
    "query_type": "amenity_search",
    "processing_time": 0.5
  }
}
```

## 🐛 Common Issues

### 401 Unauthorized
- Make sure JWT token is set in Authorization header
- Check if token is expired (login again)

### 404 Not Found  
- Verify session_id and message_id are correct
- Check if session belongs to authenticated user

### Empty Hotels Array
- Make sure you have hotels in database with `is_approved='approved'`
- Try different search terms (Sydney, Melbourne, Brisbane, etc.)

## ⚡ Quick Test Commands

```bash
# Check if API is running
curl http://localhost:8000/api/chat/sessions/

# Test with token  
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/chat/sessions/
```

## 📊 Database Check

```bash
# Check chat data in Docker
docker-compose exec web python manage.py shell -c "
from ai_chat.models import ChatSession, ChatMessage
print(f'Sessions: {ChatSession.objects.count()}')
print(f'Messages: {ChatMessage.objects.count()}')
"
```