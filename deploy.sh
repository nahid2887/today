#!/bin/bash

# Quick Deploy Script with HTTPS
# Domains: app.tri2directaitravel.com.au & chat.tri2directaitravel.com.au

set -e

EMAIL="admin@tri2directaitravel.com.au"  # Change to your email

echo "=========================================="
echo "  Deploying with HTTPS"
echo "=========================================="

# Create directories
mkdir -p certbot/www certbot/conf nginx/conf.d

# Use HTTP-only config initially
echo "Setting up initial HTTP config..."
cp -f nginx/conf.d-init/*.conf nginx/conf.d/

# Stop existing containers
echo "Stopping existing containers..."
docker compose down 2>/dev/null || true

# Build and start
echo "Building and starting services..."
docker compose build
docker compose up -d

# Wait for services
echo "Waiting for services to start (60 seconds)..."
sleep 60

# Check services
echo ""
echo "Service Status:"
docker compose ps

# Get SSL certificates
echo ""
echo "Obtaining SSL certificate for app.tri2directaitravel.com.au..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d app.tri2directaitravel.com.au || echo "Failed for app domain"

echo ""
echo "Obtaining SSL certificate for chat.tri2directaitravel.com.au..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d chat.tri2directaitravel.com.au || echo "Failed for chat domain"

# Check if certificates exist
if [ -f "certbot/conf/live/app.tri2directaitravel.com.au/fullchain.pem" ] && \
   [ -f "certbot/conf/live/chat.tri2directaitravel.com.au/fullchain.pem" ]; then
    
    echo ""
    echo "SSL certificates obtained! Switching to HTTPS config..."
    
    # Copy HTTPS configs
    cp -f nginx/conf.d-ssl/*.conf nginx/conf.d/ 2>/dev/null || {
        # Create HTTPS configs inline
        cat > nginx/conf.d/app.conf << 'EOF'
server {
    listen 80;
    server_name app.tri2directaitravel.com.au;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl http2;
    server_name app.tri2directaitravel.com.au;
    ssl_certificate /etc/letsencrypt/live/app.tri2directaitravel.com.au/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.tri2directaitravel.com.au/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
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
    }
    location /static/ { alias /app/static/; }
    location /media/ { alias /app/media/; }
}
EOF

        cat > nginx/conf.d/chat.conf << 'EOF'
server {
    listen 80;
    server_name chat.tri2directaitravel.com.au;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl http2;
    server_name chat.tri2directaitravel.com.au;
    ssl_certificate /etc/letsencrypt/live/chat.tri2directaitravel.com.au/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.tri2directaitravel.com.au/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
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
        proxy_read_timeout 86400;
    }
}
EOF

        cat > nginx/conf.d/default.conf << 'EOF'
server {
    listen 80 default_server;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 444; }
}
EOF
    }
    
    # Reload nginx
    docker compose exec nginx nginx -s reload
    
    echo ""
    echo "=========================================="
    echo "  HTTPS Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Your sites are now available at:"
    echo "  https://app.tri2directaitravel.com.au"
    echo "  https://chat.tri2directaitravel.com.au"
    
else
    echo ""
    echo "=========================================="
    echo "  Running on HTTP only"
    echo "=========================================="
    echo ""
    echo "SSL certificates not obtained. Sites available at:"
    echo "  http://app.tri2directaitravel.com.au"
    echo "  http://chat.tri2directaitravel.com.au"
    echo ""
    echo "Make sure DNS is pointing to this server, then run:"
    echo "  ./setup-ssl.sh"
fi

echo ""
echo "Run migrations:"
echo "  docker compose exec web python manage.py migrate"
echo ""
echo "View logs:"
echo "  docker compose logs -f"
