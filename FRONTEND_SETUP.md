# Frontend API Access Guide

## For Local Frontend (Same Windows Machine)

Use these URLs directly in your frontend:

```javascript
// React/Vue/Angular example
const API_BASE = 'http://localhost:8000';
const CHAT_API_BASE = 'http://localhost:8001';

// Register
fetch(`${API_BASE}/api/auth/register/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'Password123',
    password_confirm: 'Password123',
    full_name: 'User Name'
  })
});

// Login
fetch(`${API_BASE}/api/auth/login/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'Password123'
  })
});

// Send chat (use token from login response)
fetch(`${CHAT_API_BASE}/api/chat/send/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_ACCESS_TOKEN'
  },
  body: JSON.stringify({
    content: 'Find me a hotel in Philadelphia'
  })
});

// Get chat history
fetch(`${CHAT_API_BASE}/api/chat/messages/?page=1&limit=10`, {
  headers: {
    'Authorization': 'Bearer YOUR_ACCESS_TOKEN'
  }
});
```

---

## For Frontend on Different Network Machine

If your frontend is running on a **different computer** on the network:

### Option 1: Use Machine Hostname (Recommended)

Find your Windows machine's hostname:
```bash
hostname
```

Then use:
```javascript
const API_BASE = 'http://YOUR-HOSTNAME:8000';
const CHAT_API_BASE = 'http://YOUR-HOSTNAME:8001';
```

Example: `http://DESKTOP-ABC123:8000/api/auth/register/`

### Option 2: Use Network IP with Port Forwarding

If hostname doesn't work, use your network IP:
```javascript
const API_BASE = 'http://10.10.13.27:8000';
const CHAT_API_BASE = 'http://10.10.13.27:8001';
```

This requires port forwarding at Windows firewall level.

---

## CORS Configuration

Both APIs have CORS enabled (`allow_origins=["*"]`), so cross-origin requests will work.

---

## API Endpoints Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/register/` | POST | No | Register new user |
| `/api/auth/login/` | POST | No | Login and get token |
| `/api/chat/send/` | POST | Yes | Send chat message |
| `/api/chat/messages/` | GET | Yes | Get chat history |
| `/docs` | GET | No | FastAPI Swagger docs |
| `/api/docs/` | GET | No | Django DRF docs |

---

## Postman/Insomnia Setup

If using Postman or Insomnia:

1. **Register:**
   ```
   POST http://localhost:8000/api/auth/register/
   Body (JSON):
   {
     "email": "user@example.com",
     "password": "Password123",
     "password_confirm": "Password123",
     "full_name": "User Name"
   }
   ```

2. **Login:**
   ```
   POST http://localhost:8000/api/auth/login/
   Body (JSON):
   {
     "email": "user@example.com",
     "password": "Password123"
   }
   Response: { "access_token": "...", "refresh_token": "..." }
   ```

3. **Send Chat:**
   ```
   POST http://localhost:8001/api/chat/send/
   Headers:
     Authorization: Bearer <access_token>
   Body (JSON):
   {
     "content": "Find me a hotel in Philadelphia with a pool"
   }
   ```

4. **Get History:**
   ```
   GET http://localhost:8001/api/chat/messages/?page=1&limit=10
   Headers:
     Authorization: Bearer <access_token>
   ```

---

## Troubleshooting

**Problem:** Getting 404 or connection refused

**Solution:** 
- Check if services are running: `docker-compose ps`
- Use `localhost` not `127.0.0.1` or `10.10.13.27` (these don't work from Windows)
- If accessing from another machine, use the Windows machine's **hostname** instead of IP

**Problem:** CORS errors

**Solution:** 
- CORS is enabled (`*`), so this shouldn't happen
- Check if Authorization header is being sent correctly
- Ensure you're using Bearer token format: `Bearer YOUR_TOKEN`

**Problem:** Token invalid

**Solution:**
- Get a fresh token from `/api/auth/login/`
- Ensure you're using `access_token` not `refresh_token`
- Token format must be: `Authorization: Bearer <token>`
