# API Access Guide

Both services are running and accessible on the network IP `10.10.13.27`:

## Django REST API (Port 8000)
- **Base URL:** http://10.10.13.27:8000
- **Swagger Docs:** http://10.10.13.27:8000/api/docs/
- **ReDoc:** http://10.10.13.27:8000/api/redoc/

### Auth Endpoints
- **Register:** `POST /api/auth/register/`
  ```json
  {
    "email": "user@example.com",
    "password": "Test@12345",
    "password_confirm": "Test@12345",
    "full_name": "User Name"
  }
  ```

- **Login:** `POST /api/auth/login/`
  ```json
  {
    "email": "user@example.com",
    "password": "Test@12345"
  }
  ```
  **Response:** `{"access_token": "...", "refresh_token": "...", ...}`

---

## FastAPI Chat Service (Port 8001)
- **Base URL:** http://10.10.13.27:8001
- **Swagger Docs:** http://10.10.13.27:8001/docs
- **ReDoc:** http://10.10.13.27:8001/redoc

### Chat Endpoints (Bearer Token Required)
Use the `access_token` from Django login as Bearer token.

- **Send Message:** `POST /api/chat/send/`
  ```json
  {
    "content": "find me hotel in Philadelphia with pool"
  }
  ```

- **Get History:** `GET /api/chat/messages/?page=1&limit=10`
  - Returns paginated chat history
  - `page`: Page number (default: 1)
  - `limit`: Items per page (default: 10, max: 50)

---

## Workflow

1. **Register/Login via Django**
   ```bash
   curl -X POST http://10.10.13.27:8000/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com", "password":"Test@12345"}'
   ```
   Copy the `access_token` from response.

2. **Send Chat Message**
   ```bash
   curl -X POST http://10.10.13.27:8001/api/chat/send/ \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{"content":"find me hotel in Philadelphia"}'
   ```

3. **Get Chat History**
   ```bash
   curl http://10.10.13.27:8001/api/chat/messages/?page=1&limit=10 \
     -H "Authorization: Bearer <access_token>"
   ```

---

## Services Status

```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs -f web          # Django
docker-compose logs -f ai_chat_api  # FastAPI

# Restart services
docker-compose restart web
docker-compose restart ai_chat_api
```
