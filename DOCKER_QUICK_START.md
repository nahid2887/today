# 🚀 Quick Docker HTTP Deployment Guide

## Simple HTTP Setup - No Nginx Required

### 🔧 What's Configured:
- **Django Web App**: Port 8000 (Main Application)
- **AI Chat API**: Port 8001 (AI Services)  
- **PostgreSQL Database**: Port 5432 (Database)

### 🚀 Quick Start Commands:

```bash
# Windows
./start_docker.bat

# Linux/Mac
./start_docker.sh

# Manual Docker Commands
docker-compose down -v          # Clean everything
docker-compose build --no-cache # Fresh build
docker-compose up -d            # Start in background
```

### 📍 Service URLs:
- **Main Web App**: http://localhost:8000
- **AI Chat API**: http://localhost:8001/docs (FastAPI docs)
- **Database**: localhost:5432

### 📊 Monitoring Commands:
```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f ai_chat_api
docker-compose logs -f db

# Restart services
docker-compose restart

# Stop everything
docker-compose down
```

### 🔧 Configuration Details:

**Database Connection:**
- Host: localhost
- Port: 5432 
- Database: hotel_db
- Username: hotel_user
- Password: hotel_pass

**Environment Variables:**
- Django runs in DEBUG mode
- Database uses internal Docker networking
- All services restart automatically unless stopped

### 🛠️ Development Mode:
- Code is mounted as volumes (live reload)
- PostgreSQL data is persistent
- No nginx complexity - direct HTTP access

### ⚡ Performance Notes:
- First build takes time (downloading ML models ~2GB)
- Subsequent starts are fast
- All services run in background

### 🔍 Troubleshooting:
```bash
# If build fails
docker-compose down -v
docker system prune -f
docker-compose build --no-cache

# If ports are busy
netstat -ano | findstr :8000
netstat -ano | findstr :8001
```

Ready to go! 🎉