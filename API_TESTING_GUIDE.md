# AIHotel Chat API - Postman Testing Guide

## 🚀 Quick Start

Your AI Chat API is **WORKING** and ready to test! Here's how to use it in Postman:

### 1. Import the Postman Collection

1. Open Postman
2. Click **Import** button
3. Select the file: `AI_CHAT_POSTMAN_COLLECTION.json`
4. The collection "AI Hotel Chat API" will be imported

### 2. Authentication Setup

**Test User Credentials:**
- **Username:** `apitest`
- **Password:** `testpass123`
- **JWT Token:** Already configured in collection variables

### 3. API Testing Flow

#### Step 1: Get JWT Token (Optional - already set)
```
POST http://localhost:8000/api/auth/login/
{
    "username": "apitest",
    "password": "testpass123"
}
```

#### Step 2: Create Chat Session
```
POST http://localhost:8000/api/chat/sessions/
{
    "title": "Hotel Recommendation Chat",
    "metadata": {
        "location": "New York",
        "budget": "luxury"
    }
}
```

**Response Example:**
```json
{
    "id": 3,
    "title": "Hotel Recommendation Chat",
    "status": "active",
    "metadata": {"location": "New York", "budget": "luxury"},
    "shown_hotel_ids": [],
    "last_hotels": [],
    "messages": [],
    "message_count": 0,
    "created_at": "2025-02-12T..."
}
```

#### Step 3: Send Message (Start AI Chat)
```
POST http://localhost:8000/api/chat/sessions/{session_id}/send/
{
    "content": "I need a luxury hotel in New York with spa and pool facilities"
}
```

**Response Example:**
```json
{
    "user_message_id": 5,
    "assistant_message_id": 6,
    "session_id": 3,
    "status": "processing"
}
```

#### Step 4: Get Messages
```
GET http://localhost:8000/api/chat/sessions/{session_id}/messages/
```

**Response will show:**
- Your user message
- AI assistant response with hotel recommendations
- Streamed chunks of the response
- Recommended hotels with details

## 🎯 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login/` | Get JWT token |
| `GET` | `/api/chat/sessions/` | List all chat sessions |
| `POST` | `/api/chat/sessions/` | Create new chat session |
| `GET` | `/api/chat/sessions/{id}/` | Get session details |
| `POST` | `/api/chat/sessions/{id}/send/` | Send message to AI |
| `GET` | `/api/chat/sessions/{id}/messages/` | Get all messages |
| `GET` | `/api/chat/sessions/{id}/messages/{msg_id}/stream/` | Stream AI response (SSE) |
| `POST` | `/api/chat/messages/{msg_id}/hotels/{hotel_id}/clicked/` | Track hotel clicks |
| `POST` | `/api/chat/messages/{msg_id}/hotels/{hotel_id}/booked/` | Track hotel bookings |

## 🔥 AI Features Working

### ✅ What's Working:
- **JWT Authentication**: Bearer token authentication
- **Chat Sessions**: Create and manage chat sessions
- **AI Responses**: Intelligent hotel recommendations
- **Chunk Streaming**: Messages saved chunk by chunk
- **Hotel Recommendations**: Real hotel data from database
- **Hotel Tracking**: Click and booking analytics
- **Context Awareness**: AI remembers conversation context

### 📊 AI Response Features:
- **Location-based search**: "Find hotels in Paris"
- **Budget filtering**: "Luxury hotels", "Budget options"
- **Amenity matching**: "Hotels with spa", "Pool facilities"
- **Rating filtering**: "4+ star hotels"
- **Real-time recommendations**: Connected to hotel database

## 🛠️ Testing Examples

### Example 1: Luxury Hotels
```json
{
    "content": "I need luxury hotels in Paris with spa facilities"
}
```

### Example 2: Budget Travel
```json
{
    "content": "Find me budget-friendly hotels in Tokyo near train stations"
}
```

### Example 3: Business Travel
```json
{
    "content": "I need a business hotel in New York with conference rooms and WiFi"
}
```

## 🌊 Streaming Response (SSE)

**Note:** Postman doesn't handle Server-Sent Events well. For testing streaming:

1. **Browser Testing**: Open in browser:
   ```
   http://localhost:8000/api/chat/sessions/2/messages/2/stream/
   ```

2. **Curl Testing**:
   ```bash
   curl -N -H "Authorization: Bearer YOUR_TOKEN" \
        -H "Accept: text/event-stream" \
        "http://localhost:8000/api/chat/sessions/2/messages/2/stream/"
   ```

## 📱 Hotel Interaction Tracking

After AI recommends hotels, track user interactions:

### Mark Hotel as Clicked:
```
POST /api/chat/messages/{message_id}/hotels/{hotel_id}/clicked/
{}
```

### Mark Hotel as Booked:
```
POST /api/chat/messages/{message_id}/hotels/{hotel_id}/booked/
{
    "booking_details": {
        "check_in": "2025-03-01",
        "check_out": "2025-03-05",
        "guests": 2,
        "room_type": "Deluxe Suite"
    }
}
```

## 🚨 Troubleshooting

### Common Issues:

1. **401 Unauthorized**: Check JWT token in Authorization header
2. **404 Not Found**: Verify endpoint URLs (check for trailing slashes)
3. **Session ID**: Update session_id variable in Postman after creating session

### Debug Commands:
```bash
# Check if containers are running
docker-compose ps

# View logs
docker-compose logs web

# Get new JWT token
docker-compose exec web python manage.py shell
```

## 🎉 Success Indicators

When everything is working, you'll see:
- ✅ 200 OK responses
- ✅ JWT token authentication working
- ✅ Chat sessions created
- ✅ AI responses with hotel recommendations
- ✅ Messages saved with chunks
- ✅ Hotel data from your database

## 🔧 Collection Variables

Update these in Postman:
- `base_url`: http://localhost:8000
- `jwt_token`: Your JWT token (already set)
- `session_id`: Update after creating session
- `message_id`: Update after sending message

---

**Ready to test!** 🚀 Import the collection and start testing your AI chat system!