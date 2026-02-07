# Hotel Verification WebSocket API Documentation

## Overview
Partners receive real-time notifications when their hotel applications are approved or rejected.

## WebSocket Connection

### URL Pattern
```
ws://localhost:8000/ws/partner/{user_id}/
```

### Example Connection (JavaScript)
```javascript
const userId = 1; // Partner/User ID
const ws = new WebSocket(`ws://localhost:8000/ws/partner/${userId}/`);

ws.onopen = function(event) {
    console.log('WebSocket connection established');
};

ws.onmessage = function(event) {
    const notification = JSON.parse(event.data);
    console.log('Notification received:', notification);
    
    // Handle different notification types
    if (notification.type === 'hotel_approved') {
        console.log(`Hotel "${notification.hotel_name}" has been approved!`);
    } else if (notification.type === 'hotel_rejected') {
        console.log(`Hotel "${notification.hotel_name}" was rejected`);
        console.log(`Reason: ${notification.reason}`);
    }
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

ws.onclose = function(event) {
    console.log('WebSocket connection closed');
};
```

## Notification Payload

### Hotel Approved
```json
{
    "type": "hotel_approved",
    "hotel_id": 1,
    "hotel_name": "Mountain View Lodge",
    "status": "approved",
    "reason": null,
    "timestamp": "2026-02-07T10:30:45.123456",
    "message": "Your hotel \"Mountain View Lodge\" has been approved!"
}
```

### Hotel Rejected
```json
{
    "type": "hotel_rejected",
    "hotel_id": 2,
    "hotel_name": "Historic Harbor Inn",
    "status": "rejected",
    "reason": "Insufficient amenities - required: WiFi, Gym, Restaurant",
    "timestamp": "2026-02-07T10:35:22.654321",
    "message": "Your hotel \"Historic Harbor Inn\" has been rejected. Reason: Insufficient amenities - required: WiFi, Gym, Restaurant"
}
```

## REST API Endpoints

### Reject Hotel with Reason
```
POST /api/superadmin/hotels/{id}/reject/
```

**Request Body:**
```json
{
    "reason": "Insufficient amenities or other reason for rejection"
}
```

**Response:**
```json
{
    "message": "Hotel rejected",
    "reason": "Insufficient amenities or other reason for rejection",
    "hotel": {
        "id": 1,
        "hotel_name": "Test Hotel",
        "is_approved": "rejected",
        "rejection_reason": "Insufficient amenities or other reason for rejection",
        ...
    }
}
```

### Approve Hotel
```
POST /api/superadmin/hotels/{id}/approve/
```

**Response:**
```json
{
    "message": "Hotel approved successfully",
    "hotel": {
        "id": 1,
        "hotel_name": "Test Hotel",
        "is_approved": "approved",
        ...
    }
}
```

### Get Verification Statistics
```
GET /api/superadmin/hotels/stats/
```

**Response:**
```json
{
    "pending": 5,
    "approved": 12,
    "rejected": 3,
    "total": 20
}
```

### List Pending Hotels
```
GET /api/superadmin/hotels/?status=pending
```

**Response:**
```json
{
    "count": 5,
    "status": "pending",
    "results": [
        {
            "id": 1,
            "hotel_name": "Mountain View Lodge",
            "city": "Denver",
            "country": "USA",
            "partner_id": 5,
            "partner_name": "John Smith",
            "partner_email": "john@example.com",
            "is_approved": "pending",
            "rejection_reason": null,
            ...
        }
    ]
}
```

## Running the Server

Make sure to use a WebSocket-compatible ASGI server:

```bash
# Install Daphne (ASGI server)
pip install daphne

# Run the server
daphne -b 0.0.0.0 -p 8000 core.asgi:application
```

Or use Uvicorn:

```bash
pip install uvicorn
uvicorn core.asgi:application --host 0.0.0.0 --port 8000
```

## Testing with curl/Postman

### Test HTTP Rejection Endpoint
```bash
curl -X POST http://localhost:8000/api/superadmin/hotels/1/reject/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{"reason": "Insufficient amenities"}'
```

## Notes

- WebSocket connections require the user to be authenticated
- Partners receive notifications in real-time when their hotel status changes
- Rejection reasons are stored and can be retrieved via the API
- The notification system uses in-memory channels by default (suitable for development)
- For production, use Redis or other channel layers
