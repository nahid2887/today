#!/bin/bash

# SSL Setup Script for tri2directaitravel.com.au
# Run this on your VPS after deploying the docker-compose

set -e

DOMAINS=(app.tri2directaitravel.com.au chat.tri2directaitravel.com.au)
EMAIL="admin@tri2directaitravel.com.au"  # Change this to your email

echo "=============================================="
echo "  SSL Certificate Setup Script"
echo "=============================================="

# Create required directories
echo "Creating directories..."
mkdir -p certbot/www certbot/conf

# Step 1: Use initial HTTP-only nginx config
echo "Step 1: Setting up initial HTTP configuration..."
cp -r nginx/conf.d-init/* nginx/conf.d/

# Step 2: Start services with HTTP only
echo "Step 2: Starting services..."
docker compose down
docker compose up -d db
echo "Waiting for database to be ready..."
sleep 15

docker compose up -d web ai_chat_api
echo "Waiting for apps to start..."
sleep 30

docker compose up -d nginx
echo "Waiting for nginx..."
sleep 5

# Step 3: Test HTTP access
echo "Step 3: Testing HTTP access..."
for domain in "${DOMAINS[@]}"; do
    echo "Testing http://$domain..."
    curl -s -o /dev/null -w "%{http_code}" "http://$domain" || echo "Warning: $domain not responding"
done

# Step 4: Get SSL certificates
echo ""
echo "Step 4: Obtaining SSL certificates..."
for domain in "${DOMAINS[@]}"; do
    echo ""
    echo "Getting certificate for $domain..."
    docker compose run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        -d $domain
done

# Step 5: Switch to HTTPS nginx config
echo ""
echo "Step 5: Switching to HTTPS configuration..."
cat > nginx/conf.d/app.conf << 'APPEOF'
# Django App - app.tri2directaitravel.com.au

# HTTP - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name app.tri2directaitravel.com.au;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name app.tri2directaitravel.com.au;

    ssl_certificate /etc/letsencrypt/live/app.tri2directaitravel.com.au/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.tri2directaitravel.com.au/privkey.pem;

    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://web:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 30d;
        add_header Cache-Control "public";
    }
}
APPEOF

cat > nginx/conf.d/chat.conf << 'CHATEOF'
# AI Chat API - chat.tri2directaitravel.com.au

# HTTP - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name chat.tri2directaitravel.com.au;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name chat.tri2directaitravel.com.au;

    ssl_certificate /etc/letsencrypt/live/chat.tri2directaitravel.com.au/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.tri2directaitravel.com.au/privkey.pem;

    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://ai_chat_api:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /ws/ {
        proxy_pass http://ai_chat_api:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
CHATEOF

# Step 6: Reload nginx with HTTPS config
echo ""
echo "Step 6: Reloading nginx with HTTPS..."
docker compose exec nginx nginx -s reload

echo ""
echo "=============================================="
echo "  SSL Setup Complete!"
echo "=============================================="
echo ""
echo "Your sites are now available at:"
echo "  https://app.tri2directaitravel.com.au"
echo "  https://chat.tri2directaitravel.com.au"
echo ""
echo "Certificates will auto-renew via the certbot container."
