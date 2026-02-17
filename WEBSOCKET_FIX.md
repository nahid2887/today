# WebSocket Connection Fixed ✅

## Problem
WebSocket was returning 404 because Django was using WSGI server (runserver) instead of ASGI.

## Solution
Changed the Django server from `python manage.py runserver` to `daphne` (ASGI server).

### Changes Made:
1. Updated `docker-compose.yml`: Changed web service command to use Daphne
   ```
   daphne -b 0.0.0.0 -p 8000 core.asgi:application
   ```

2. Fixed `core/asgi.py`: Changed import from `notifications.routing` to `core.routing`

3. Rebuilt Docker container with Daphne support

---

## Testing Results

**WebSocket Handshake Test:**
```bash
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:8000/ws/partner/96/
```

**Response:**
```
HTTP/1.1 101 Switching Protocols  ✅
Server: daphne
Upgrade: WebSocket
Connection: Upgrade
```

---

## How to Connect in Postman

1. **URL:** `ws://localhost:8000/ws/partner/96/`
2. **Click Connect** button
3. **You should see:**
   - "Connected" status
   - Any pending notifications will be received automatically

---

## How to Connect in Browser Console

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/partner/96/');

ws.onopen = () => {
  console.log('✅ Connected to notifications');
};

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  console.log('📬 Notification received:', notification);
};

ws.onerror = (error) => {
  console.error('❌ Connection error:', error);
};

ws.onclose = () => {
  console.log('❌ Disconnected from notifications');
};
```

---

## API Endpoints Still Available

All REST API endpoints work normally:
- `GET /api/hotel/notifications/`
- `PATCH /api/hotel/notifications/{id}/`
- `POST /api/hotel/notifications/mark-all-read/`
- etc.

---

## Status

✅ WebSocket running on Daphne  
✅ ASGI routing configured  
✅ All services running  
✅ Ready for partner notifications  

Try connecting in Postman to `ws://localhost:8000/ws/partner/96/` now!
