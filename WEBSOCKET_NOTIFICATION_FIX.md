# WebSocket Notification Fix ✅

## Problem Fixed
The WebSocket consumer was not receiving approval/rejection notifications because:
- **Consumer was listening for**: `hotel_approved`, `hotel_rejected` message types
- **Views were sending**: `hotel_notification` message type
- **Result**: Message mismatch → 1011 Server Error

## Solution Applied

### Updated `core/core/consumers.py`

Added a unified `hotel_notification()` handler that:
1. Receives the `'hotel_notification'` message type from views
2. Extracts notification type from event data
3. Sends properly formatted message to client with approval/rejection details

```python
async def hotel_notification(self, event):
    """Receive hotel notification message from group - handles approve/reject"""
    notification_type = event.get('notification_type', 'unknown')
    
    message_data = {
        'type': notification_type,
        'hotel_id': event.get('hotel_id'),
        'hotel_name': event.get('hotel_name'),
        'status': event.get('status'),
        'timestamp': event.get('timestamp'),
        'message': event.get('message')
    }
    
    # Add reason if rejection
    if notification_type == 'hotel_rejected' and event.get('reason'):
        message_data['reason'] = event['reason']
    
    await self.send(text_data=json.dumps(message_data))
```

---

## Now It Works!

### Flow Diagram
```
Admin Approves Hotel
        ↓
superadmin/views.py approve() method
        ↓
Notification.objects.create() → Database ✅
        ↓
send_websocket_notification() with type='hotel_notification'
        ↓
channel_layer.group_send(partner_{user_id})
        ↓
consumers.py hotel_notification() handler ✅
        ↓
client receives: {type: 'hotel_approved', hotel_id: 22, ...}
```

---

## Test It Now

### Option 1: WebSocket Real-Time (Browser/Postman)

1. **Connect WebSocket**
   ```
   ws://localhost:8000/ws/partner/96/
   ```

2. **In another tab, approve hotel via API**
   ```bash
   curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/22/approve/ \
     -H "Authorization: Bearer ADMIN_TOKEN" \
     -H "Content-Type: application/json"
   ```

3. **Check WebSocket response** - Should receive:
   ```json
   {
     "type": "hotel_approved",
     "hotel_id": 22,
     "hotel_name": "Beautiful Hotel",
     "status": "approved",
     "timestamp": "2026-02-17T04:10:00Z",
     "message": "Your hotel \"Beautiful Hotel\" has been approved!"
   }
   ```

### Option 2: REST API

After approval, partner checks notifications:
```bash
curl http://10.10.13.27:8002/api/hotel/notifications/ \
  -H "Authorization: Bearer PARTNER_TOKEN"
```

Response:
```json
{
  "total_count": 1,
  "unread_count": 1,
  "results": [
    {
      "id": 1,
      "type": "hotel_approved",
      "title": "Hotel Approved",
      "message": "Your hotel \"Beautiful Hotel\" has been approved!",
      "data": {
        "hotel_id": 22,
        "hotel_name": "Beautiful Hotel"
      },
      "read": false,
      "created_at": "2026-02-17T04:10:00Z"
    }
  ]
}
```

---

## Rejection Flow (Same Fix)

When admin rejects:
```bash
curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/22/reject/ \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Insufficient amenities"}'
```

Partner receives WebSocket:
```json
{
  "type": "hotel_rejected",
  "hotel_id": 22,
  "hotel_name": "Beautiful Hotel",
  "status": "rejected",
  "reason": "Insufficient amenities",
  "message": "Your hotel \"Beautiful Hotel\" has been rejected. Reason: Insufficient amenities"
}
```

---

## Status

✅ **Fixed** - WebSocket message type mismatch resolved  
✅ **Restarted** - Django running with new consumer code  
✅ **Ready** - Test approval/rejection notifications now

