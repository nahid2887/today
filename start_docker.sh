#!/bin/bash

echo "🚀 Starting Hotel Management System with Docker..."
echo "================================="

# Stop any running containers
echo "📍 Stopping existing containers..."
docker-compose down

# Build and start all services
echo "🏗️  Building and starting services..."
docker-compose up --build -d

echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "📊 Checking service status..."
docker-compose ps

echo ""
echo "✅ Services are running!"
echo "================================="
echo "🌐 Django Web App: http://localhost:8000"
echo "🤖 AI Chat API: http://localhost:8001"
echo "🗃️  PostgreSQL Database: localhost:5432"
echo "================================="
echo ""
echo "💡 To check logs: docker-compose logs -f [service_name]"
echo "🛑 To stop: docker-compose down"
echo "🔄 To restart: docker-compose restart"