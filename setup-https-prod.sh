#!/bin/bash

# Production HTTPS Setup Script
# Domains: app.tri2directaitravel.com.au & chat.tri2directaitravel.com.au
# Email: nahid23@gmail.com

set -e

EMAIL="nahid23@gmail.com"
DOMAINS=("app.tri2directaitravel.com.au" "chat.tri2directaitravel.com.au")

echo "=========================================="
echo "  Production HTTPS Setup"
echo "=========================================="

# Create directories
mkdir -p certbot/www/.well-known/acme-challenge
mkdir -p certbot/conf

# Step 1: Start services with HTTP only
echo ""
echo "Step 1: Starting services..."
docker compose -f docker-compose-prod.yml up -d db
sleep 20
docker compose -f docker-compose-prod.yml up -d web ai_chat_api
sleep 30
docker compose -f docker-compose-prod.yml up -d nginx

echo "Waiting for nginx to be ready..."
sleep 10

# Step 2: Test HTTP access
echo ""
echo "Step 2: Testing HTTP access..."
for domain in "${DOMAINS[@]}"; do
    echo "Testing http://$domain..."
    curl -s -I "http://$domain" | head -1 || echo "⚠️  $domain not responding (expected if DNS not propagated)"
done

# Step 3: Get SSL certificates
echo ""
echo "Step 3: Obtaining SSL certificates from Let's Encrypt..."

for domain in "${DOMAINS[@]}"; do
    echo ""
    echo "Getting certificate for $domain..."
    
    docker compose -f docker-compose-prod.yml run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d "$domain" || {
            echo "⚠️  Certificate fetch failed for $domain"
            echo "Make sure DNS is configured correctly:"
            echo "  - app.tri2directaitravel.com.au -> 76.13.195.67"
            echo "  - chat.tri2directaitravel.com.au -> 76.13.195.67"
            exit 1
        }
done

# Step 4: Verify certificates
echo ""
echo "Step 4: Verifying certificates..."
ls -la certbot/conf/live/

# Step 5: Reload nginx with HTTPS
echo ""
echo "Step 5: Reloading nginx with HTTPS configuration..."
docker compose -f docker-compose-prod.yml exec nginx nginx -s reload

# Step 6: Test HTTPS
echo ""
echo "Step 6: Testing HTTPS..."
sleep 5

for domain in "${DOMAINS[@]}"; do
    echo "Testing https://$domain..."
    curl -s -I "https://$domain" | head -1 || echo "⚠️  $domain not responding"
done

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "✅ Your sites are now available at:"
echo "   https://app.tri2directaitravel.com.au"
echo "   https://chat.tri2directaitravel.com.au"
echo ""
echo "SSL certificates will auto-renew via certbot container"
echo ""
echo "View logs: docker compose -f docker-compose-prod.yml logs -f"
