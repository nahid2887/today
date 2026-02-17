# AI Hotel Chat System

A real-time streaming AI chat system for hotel recommendations, integrated with the Django hotel booking platform.

## Features

✅ **Real-time Streaming Chat**: AI responses stream chunk by chunk like ChatGPT  
✅ **Hotel Recommendations**: AI suggests hotels from your database based on user queries  
✅ **Session Management**: Persistent chat sessions for travelers  
✅ **Context Awareness**: AI remembers conversation history and previously shown hotels  
✅ **Hotel Tracking**: Track which hotels users click on and book  
✅ **RESTful API**: Complete REST API for chat functionality  
✅ **Admin Interface**: Django admin for managing chats and recommendations  
✅ **Dockerized**: Ready for deployment with Docker Compose  

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django API    │    │   AI Service    │
│   (Your App)    │◄──►│   (ai_chat app) │◄──►│   (Streaming)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   PostgreSQL    │
                       │   Database      │
                       └─────────────────┘
```

## API Endpoints

### Chat Sessions
- `GET /api/chat/sessions/` - List all chat sessions
- `POST /api/chat/sessions/` - Create new chat session
- `GET /api/chat/sessions/{id}/` - Get specific session
- `PUT /api/chat/sessions/{id}/` - Update session
- `DELETE /api/chat/sessions/{id}/` - Archive session

### Chat Messages
- `GET /api/chat/sessions/{id}/messages/` - List messages in session
- `POST /api/chat/sessions/{id}/send/` - Send message (returns immediately)
- `GET /api/chat/sessions/{id}/messages/{msg_id}/stream/` - Stream AI response (SSE)

### Hotel Interaction Tracking
- `POST /api/chat/messages/{id}/hotels/{hotel_id}/clicked/` - Mark hotel as clicked
- `POST /api/chat/messages/{id}/hotels/{hotel_id}/booked/` - Mark hotel as booked

## Usage Examples

### 1. Create Chat Session
```bash
curl -X POST http://localhost:8000/api/chat/sessions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 2. Send Message
```bash
curl -X POST http://localhost:8000/api/chat/sessions/1/send/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "I need a hotel in Sydney with a pool"}'
```

Response:
```json
{
  "user_message_id": 1,
  "assistant_message_id": 2,
  "session_id": 1,
  "status": "processing"
}
```

### 3. Stream AI Response (Server-Sent Events)
```javascript
const eventSource = new EventSource(
  '/api/chat/sessions/1/messages/2/stream/',
  { headers: { 'Authorization': 'Bearer YOUR_TOKEN' } }
);

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.chunk) {
    // Append chunk to UI
    appendText(data.chunk);
  }
  
  if (data.is_complete) {
    // Show recommended hotels
    showHotels(data.recommended_hotels);
    eventSource.close();
  }
};
```

### 4. Example Streaming Response
```json
// Chunk 1
{"chunk": "Great choice! I've found some excellent", "is_complete": false}

// Chunk 2  
{"chunk": "hotels in Sydney with pools. Here", "is_complete": false}

// Final chunk
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

## Frontend Integration

### React Example
```jsx
import { useState, useEffect } from 'react';

function ChatMessage({ sessionId, messageId }) {
  const [content, setContent] = useState('');
  const [hotels, setHotels] = useState([]);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/chat/sessions/${sessionId}/messages/${messageId}/stream/`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.chunk) {
        setContent(prev => prev + data.chunk);
      }
      
      if (data.is_complete) {
        setHotels(data.recommended_hotels || []);
        setIsComplete(true);
        eventSource.close();
      }
    };

    return () => eventSource.close();
  }, [sessionId, messageId]);

  return (
    <div className="chat-message">
      <div className="ai-response">
        {content}
        {!isComplete && <span className="typing-indicator">▊</span>}
      </div>
      
      {hotels.length > 0 && (
        <div className="hotel-recommendations">
          {hotels.map(hotel => (
            <HotelCard 
              key={hotel.id} 
              hotel={hotel}
              onSelect={() => markHotelClicked(messageId, hotel.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

## Database Models

### ChatSession
- **traveler**: User who owns the session
- **title**: Auto-generated from first message
- **status**: active/archived/deleted
- **metadata**: Session preferences and context
- **shown_hotel_ids**: Track displayed hotels for continuity
- **last_hotels**: Last recommended hotels for context

### ChatMessage  
- **session**: Parent chat session
- **role**: user/assistant/system
- **content**: Message text
- **chunks**: Streaming chunks for gradual building
- **recommended_hotels**: Hotels suggested in this message
- **is_streaming/is_complete**: Streaming status flags

### HotelRecommendation
- **message**: Parent message
- **hotel_id**: Referenced hotel ID
- **relevance_score**: AI confidence score
- **match_reason**: Why this hotel was recommended
- **was_clicked/was_booked**: User interaction tracking

## AI Response Generation

The AI service analyzes user queries and:

1. **Classifies query type**: location, budget, amenity, quality search
2. **Generates contextual response**: Appropriate intro text
3. **Queries hotel database**: Filters based on query and excludes shown hotels
4. **Ranks results**: By relevance score and ratings
5. **Streams response**: Chunk by chunk with final hotel data

### Query Classification Examples

| Query | Type | Response Style |
|-------|------|----------------|
| "Hotels in Sydney" | location_search | "Great choice! I've found excellent hotels in Sydney..." |
| "Budget friendly options" | budget_search | "I understand your budget preferences! Here are great value..." |  
| "Hotels with pools" | amenity_search | "Perfect! I've found hotels with the specific amenities..." |
| "Best rated hotels" | quality_search | "Excellent! I've selected the highest-rated hotels..." |

## Deployment

### Development
```bash
# Start services
docker-compose up -d

# Run migrations  
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### Production
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

## Environment Variables

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database  
DB_NAME=hotel_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=db
DB_PORT=5432

# AI Configuration
AI_CHUNK_SIZE=8
AI_STREAM_DELAY=0.2
AI_MAX_HOTELS=3
```

## Monitoring & Analytics

The system tracks:
- **Chat sessions** per user
- **Message volume** and response times  
- **Hotel click-through rates** from recommendations
- **Booking conversion** from chat recommendations
- **Popular queries** and search patterns

## Future Enhancements

🔄 **Real AI Integration**: Replace simulated responses with actual LLM (OpenAI, Claude, etc.)  
🔄 **Vector Search**: Semantic hotel search using embeddings  
🔄 **Multi-language**: Support for multiple languages  
🔄 **Voice Chat**: Speech-to-text and text-to-speech  
🔄 **Rich Media**: Send images, maps, and rich cards  
🔄 **Chat Export**: Export conversations as PDF/email  
🔄 **Smart Notifications**: Proactive hotel suggestions  

## Support

For issues and questions:
- Check the Django admin at `/admin/` 
- View logs with `docker-compose logs web`
- Monitor database with your preferred PostgreSQL client
- API documentation at `/api/docs/`