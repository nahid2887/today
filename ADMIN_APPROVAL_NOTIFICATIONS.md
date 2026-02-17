# Admin Hotel Approval → Partner Notifications

## How It Works

When an admin **approves** or **rejects** a hotel in the admin dashboard:

```
Admin Dashboard → Approve/Reject Hotel → 2 Things Happen:
├─ 1. Database Notification Created
└─ 2. WebSocket Message Sent to Partner
```

---

## Flow Diagram

```
┌─────────────────────────────────────┐
│   Admin Dashboard                   │
│   /admin/dashboard/hotel-verification
└────────────────┬────────────────────┘
                 │ Click Approve/Reject
                 ▼
┌─────────────────────────────────────┐
│   POST /api/superadmin/hotels/{id}/ │
│   /approve  or  /reject             │
└────────────────┬────────────────────┘
                 │ Hotel Status Updated
                 ▼
        ┌────────┴─────────┐
        │                  │
        ▼                  ▼
   ┌─────────────┐   ┌─────────────────┐
   │ Database    │   │ WebSocket       │
   │ Notification│   │ Real-time Msg   │
   │ Created     │   │ Sent to Partner │
   └──────┬──────┘   └────────┬────────┘
          │                   │
          ├─→ Partner sees it in:
          │
          ├─ REST API: /api/hotel/notifications/
          └─ WebSocket: ws://localhost:8000/ws/partner/96/
```

---

## Admin Endpoints

### Approve Hotel

**Endpoint:** `POST /api/superadmin/hotels/{hotel_id}/approve/`

**Request:**
```bash
curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/22/approve/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "message": "Hotel approved successfully",
  "hotel": {
    "id": 22,
    "hotel_name": "My Beautiful Hotel",
    "is_approved": "approved",
    ...
  }
}
```

**What Happens:**
1. ✅ Hotel `is_approved` set to `'approved'`
2. ✅ Notification created in database
3. ✅ WebSocket message sent to partner (user_id)

---

### Reject Hotel

**Endpoint:** `POST /api/superadmin/hotels/{hotel_id}/reject/`

**Request:**
```bash
curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/22/reject/ \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Insufficient amenities"}'
```

**Response:**
```json
{
  "message": "Hotel rejected",
  "reason": "Insufficient amenities",
  "hotel": {
    "id": 22,
    "hotel_name": "My Beautiful Hotel",
    "is_approved": "rejected",
    "rejection_reason": "Insufficient amenities",
    ...
  }
}
```

**What Happens:**
1. ✅ Hotel `is_approved` set to `'rejected'`
2. ✅ Hotel `rejection_reason` saved
3. ✅ Notification created with rejection reason
4. ✅ WebSocket message sent to partner

---

## Partner Receives Notification

### Via REST API

**Endpoint:** `GET /api/hotel/notifications/`

After admin approves, partner can:
```bash
curl http://10.10.13.27:8002/api/hotel/notifications/ \
  -H "Authorization: Bearer PARTNER_TOKEN"
```

**Response:**
```json
{
  "total_count": 1,
  "unread_count": 1,
  "results": [
    {
      "id": 1,
      "type": "hotel_approved",
      "title": "Hotel Approved",
      "message": "Your hotel \"My Beautiful Hotel\" has been approved!",
      "data": {
        "hotel_id": 22,
        "hotel_name": "My Beautiful Hotel"
      },
      "hotel_id": 22,
      "read": false,
      "created_at": "2026-02-17T04:00:00Z"
    }
  ]
}
```

---

### Via WebSocket (Real-Time)

Partner connects to WebSocket:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/partner/96/');

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  console.log('Type:', notification.type);
  // {
  //   "type": "hotel_approved",
  //   "hotel_id": 22,
  //   "hotel_name": "My Beautiful Hotel",
  //   "message": "Your hotel \"My Beautiful Hotel\" has been approved!",
  //   "timestamp": "2026-02-17T04:00:00Z"
  // }
};
```

---

## Notification Data Structure

### Hotel Approved
```json
{
  "type": "hotel_approved",
  "title": "Hotel Approved",
  "message": "Your hotel \"[Hotel Name]\" has been approved!",
  "data": {
    "hotel_id": 22,
    "hotel_name": "My Beautiful Hotel"
  }
}
```

### Hotel Rejected
```json
{
  "type": "hotel_rejected",
  "title": "Hotel Rejected",
  "message": "Your hotel \"[Hotel Name]\" has been rejected. Reason: [Reason]",
  "data": {
    "hotel_id": 22,
    "hotel_name": "My Beautiful Hotel",
    "reason": "Insufficient amenities"
  }
}
```

---

## Testing

### 1. Test Admin Approval

**Prerequisites:**
- Have an admin account with token
- Have a pending hotel (is_approved='pending')

**Step 1: Approve Hotel**
```bash
curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/22/approve/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Step 2: Check Partner REST API**
```bash
curl http://10.10.13.27:8002/api/hotel/notifications/ \
  -H "Authorization: Bearer PARTNER_TOKEN"
```
✅ Should see approval notification

**Step 3: Check WebSocket (Real-Time)**
```javascript
ws = new WebSocket('ws://localhost:8000/ws/partner/96/');
// Should immediately receive notification message
```

---

### 2. Test Admin Rejection

**Step 1: Reject Hotel**
```bash
curl -X POST http://10.10.13.27:8002/api/superadmin/hotels/23/reject/ \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Images not clear enough"}'
```

**Step 2: Check Partner REST API**
```bash
curl http://10.10.13.27:8002/api/hotel/notifications/ \
  -H "Authorization: Bearer PARTNER_TOKEN"
```
✅ Should see rejection notification with reason

---

## Database Tables

### hotel_notification
```
id          | user_id | hotel_id | notification_type | title          | message              | read | created_at
------------|---------|----------|-------------------|----------------|----------------------|------|----------
1           | 96      | 22       | hotel_approved    | Hotel Approved | Your hotel... has been approved! | false | 2026-02-17...
2           | 96      | 23       | hotel_rejected    | Hotel Rejected | Your hotel... has been rejected. Reason: Images not clear enough | false | 2026-02-17...
```

---

## Files Modified

1. **core/superadmin/views.py**
   - Added `Notification` model import
   - Added notification creation in `approve()` method
   - Added notification creation in `reject()` method

2. **core/hotel/models.py**
   - Added `Notification` model class

3. **core/core/consumers.py**
   - WebSocket consumer to handle real-time notifications

4. **core/core/routing.py**
   - WebSocket URL routing configuration

5. **core/core/asgi.py**
   - Updated to use Daphne ASGI server

---

## Status

✅ Admin approval → Notification created in database  
✅ Admin rejection → Notification created with reason  
✅ WebSocket → Real-time notification to partner  
✅ REST API → Partner can retrieve all notifications  
✅ Daphne → ASGI server running for WebSocket support  

**Everything is working!** 🎉

When admin approves/rejects hotel → Partner gets instant notification on both REST API and WebSocket.
