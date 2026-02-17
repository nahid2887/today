# Partner Notification System - API Documentation

## Overview

The notification system allows partners to receive real-time updates about their hotel's approval status, new bookings, and other important events through both WebSocket and REST API.

---

## WebSocket Connection

### Connect to WebSocket for Real-Time Notifications

```
ws://localhost:8000/ws/partner/{user_id}/
```

**Parameters:**
- `user_id` (integer): Your user ID from Django authentication

**Example:**
```javascript
const userId = 89;
const ws = new WebSocket(`ws://localhost:8000/ws/partner/${userId}/`);

ws.onopen = (event) => {
  console.log('Connected to partner notifications');
};

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  console.log('Received notification:', notification);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from notifications');
};
```

### Notification Types

#### 1. **Hotel Approved**
```json
{
  "type": "hotel_approved",
  "hotel_id": 22,
  "hotel_name": "My Beautiful Hotel",
  "message": "Your hotel has been approved!",
  "timestamp": "2026-02-17T02:45:53Z"
}
```

#### 2. **Hotel Rejected**
```json
{
  "type": "hotel_rejected",
  "hotel_id": 22,
  "hotel_name": "My Beautiful Hotel",
  "reason": "Missing required information",
  "timestamp": "2026-02-17T02:45:53Z"
}
```

#### 3. **Hotel Under Review**
```json
{
  "type": "hotel_pending",
  "hotel_id": 22,
  "hotel_name": "My Beautiful Hotel",
  "message": "Your hotel is under review",
  "timestamp": "2026-02-17T02:45:53Z"
}
```

#### 4. **New Booking**
```json
{
  "type": "booking_received",
  "data": {
    "booking_id": 9,
    "hotel_id": 22,
    "traveler_name": "John Doe",
    "check_in": "2026-02-20",
    "check_out": "2026-02-22",
    "total_price": 400.00
  },
  "timestamp": "2026-02-17T02:45:53Z"
}
```

#### 5. **Booking Cancelled**
```json
{
  "type": "booking_cancelled",
  "data": {
    "booking_id": 9,
    "hotel_id": 22,
    "reason": "Traveler cancelled"
  },
  "timestamp": "2026-02-17T02:45:53Z"
}
```

---

## REST API Endpoints

### 1. Get All Notifications

**Endpoint:** `GET /api/hotel/notifications/`

**Authentication:** Bearer Token (required)

**Query Parameters:**
- `unread_only` (boolean, optional): Show only unread notifications (default: false)
- `limit` (integer, optional): Number of results per page (default: 20)
- `offset` (integer, optional): Pagination offset (default: 0)

**Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://10.10.13.27:8002/api/hotel/notifications/?unread_only=true&limit=10"
```

**Response:**
```json
{
  "total_count": 5,
  "unread_count": 2,
  "limit": 10,
  "offset": 0,
  "results": [
    {
      "id": 1,
      "type": "hotel_approved",
      "title": "Hotel Approved",
      "message": "Your hotel 'My Beautiful Hotel' has been approved!",
      "data": {
        "hotel_id": 22
      },
      "hotel_id": 22,
      "read": false,
      "created_at": "2026-02-17T02:45:53Z",
      "updated_at": "2026-02-17T02:45:53Z"
    },
    {
      "id": 2,
      "type": "booking_received",
      "title": "New Booking",
      "message": "You have received a new booking for 2 nights",
      "data": {
        "booking_id": 9,
        "traveler_name": "John Doe",
        "total_price": 400.00
      },
      "hotel_id": 22,
      "read": true,
      "created_at": "2026-02-16T10:30:00Z",
      "updated_at": "2026-02-16T10:30:00Z"
    }
  ]
}
```

---

### 2. Get Single Notification

**Endpoint:** `GET /api/hotel/notifications/{notification_id}/`

**Authentication:** Bearer Token (required)

**Request:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://10.10.13.27:8002/api/hotel/notifications/1/"
```

**Response:**
```json
{
  "id": 1,
  "type": "hotel_approved",
  "title": "Hotel Approved",
  "message": "Your hotel has been approved!",
  "data": {},
  "hotel_id": 22,
  "read": false,
  "created_at": "2026-02-17T02:45:53Z",
  "updated_at": "2026-02-17T02:45:53Z"
}
```

---

### 3. Mark Notification as Read/Unread

**Endpoint:** `PATCH /api/hotel/notifications/{notification_id}/`

**Authentication:** Bearer Token (required)

**Request:**
```bash
curl -X PATCH -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_read": true}' \
  "http://10.10.13.27:8002/api/hotel/notifications/1/"
```

**Response:**
```json
{
  "id": 1,
  "type": "hotel_approved",
  "title": "Hotel Approved",
  "message": "Your hotel has been approved!",
  "data": {},
  "hotel_id": 22,
  "read": true,
  "created_at": "2026-02-17T02:45:53Z",
  "updated_at": "2026-02-17T02:45:53Z"
}
```

---

### 4. Delete Notification

**Endpoint:** `DELETE /api/hotel/notifications/{notification_id}/`

**Authentication:** Bearer Token (required)

**Request:**
```bash
curl -X DELETE -H "Authorization: Bearer YOUR_TOKEN" \
  "http://10.10.13.27:8002/api/hotel/notifications/1/"
```

**Response:** 204 No Content

---

### 5. Mark All Notifications as Read

**Endpoint:** `POST /api/hotel/notifications/mark-all-read/`

**Authentication:** Bearer Token (required)

**Request:**
```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  "http://10.10.13.27:8002/api/hotel/notifications/mark-all-read/"
```

**Response:**
```json
{
  "message": "3 notification(s) marked as read",
  "updated_count": 3
}
```

---

## Notification Types Reference

| Type | Title | Description |
|------|-------|-------------|
| `hotel_approved` | Hotel Approved | Your hotel has been approved by admin |
| `hotel_rejected` | Hotel Rejected | Your hotel submission was rejected |
| `hotel_pending` | Hotel Under Review | Your hotel is being reviewed |
| `booking_received` | New Booking | A traveler made a booking |
| `booking_cancelled` | Booking Cancelled | A booking was cancelled |
| `other` | Other | Other notifications |

---

## Frontend Integration Examples

### React Example

```jsx
import { useEffect, useState } from 'react';

function PartnerNotifications({ userId, token }) {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    // WebSocket for real-time updates
    const ws = new WebSocket(`ws://localhost:8000/ws/partner/${userId}/`);
    
    ws.onmessage = (event) => {
      const newNotification = JSON.parse(event.data);
      setNotifications(prev => [newNotification, ...prev]);
      setUnreadCount(prev => prev + 1);
    };

    return () => ws.close();
  }, [userId]);

  useEffect(() => {
    // Fetch initial notifications
    fetch(`http://localhost:8000/api/hotel/notifications/?limit=20`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        setNotifications(data.results);
        setUnreadCount(data.unread_count);
      });
  }, [token]);

  const markAsRead = async (notificationId) => {
    const res = await fetch(
      `http://localhost:8000/api/hotel/notifications/${notificationId}/`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_read: true })
      }
    );
    
    if (res.ok) {
      setNotifications(prev => prev.map(n => 
        n.id === notificationId ? { ...n, read: true } : n
      ));
      setUnreadCount(prev => Math.max(0, prev - 1));
    }
  };

  return (
    <div>
      <h2>Notifications ({unreadCount} unread)</h2>
      <ul>
        {notifications.map(notif => (
          <li 
            key={notif.id}
            className={notif.read ? 'read' : 'unread'}
          >
            <h3>{notif.title}</h3>
            <p>{notif.message}</p>
            {!notif.read && (
              <button onClick={() => markAsRead(notif.id)}>
                Mark as Read
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- **200 OK** - Successful GET/PATCH request
- **201 Created** - Successful POST request
- **204 No Content** - Successful DELETE request
- **400 Bad Request** - Invalid request data
- **401 Unauthorized** - Missing or invalid token
- **403 Forbidden** - User doesn't have permission
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

---

## Notes

- Notifications are stored in the database and persist even after server restart
- WebSocket connections are real-time; REST API is for historical data
- Pagination is supported on the list endpoint
- All timestamps are in ISO 8601 format (UTC)
- WebSocket connection automatically sends recent notifications on connect
