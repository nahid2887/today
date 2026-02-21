# HTTPS Production Deployment Guide

## Files for Production

Production HTTPS setup includes:
- `docker-compose-prod.yml` - Production docker-compose with nginx & certbot
- `nginx-prod/nginx.conf` - Main nginx configuration
- `nginx-prod/conf.d/app.conf` - Django app config with SSL
- `nginx-prod/conf.d/chat.conf` - FastAPI chat config with SSL
- `setup-https-prod.sh` - Automated setup script

## Deployment Steps

### 1. Push to GitHub

```bash
# On your local machine
cd c:\today

# Add new files
git add docker-compose-prod.yml nginx-prod/ setup-https-prod.sh

# Commit
git commit -m "Add production HTTPS configuration"

# Push
git push origin main
```

### 2. Deploy on VPS

```bash
# SSH into VPS
ssh root@76.13.195.67

# Go to project directory
cd ~/today

# Pull latest changes
git pull origin main

# Make setup script executable
chmod +x setup-https-prod.sh

# Stop current services
docker compose down

# Run setup script
./setup-https-prod.sh
```

### 3. Manual Steps (if script fails)

```bash
# Create directories
mkdir -p certbot/www/.well-known/acme-challenge
mkdir -p certbot/conf

# Start services
docker compose -f docker-compose-prod.yml up -d

# Wait for services
sleep 60

# Get certificate for app domain
docker compose -f docker-compose-prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email nahid23@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d app.tri2directaitravel.com.au

# Get certificate for chat domain
docker compose -f docker-compose-prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email nahid23@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d chat.tri2directaitravel.com.au

# Reload nginx
docker compose -f docker-compose-prod.yml exec nginx nginx -s reload

# Verify
curl -I https://app.tri2directaitravel.com.au
curl -I https://chat.tri2directaitravel.com.au
```

## Verify Everything Works

```bash
# Check services
docker compose -f docker-compose-prod.yml ps

# Check certificates
ls -la certbot/conf/live/

# View nginx logs
docker compose -f docker-compose-prod.yml logs nginx

# Test endpoints
curl https://app.tri2directaitravel.com.au
curl https://chat.tri2directaitravel.com.au/docs
```

## Auto-Renewal

Certbot container automatically renews certificates 30 days before expiry. No manual intervention needed.

## Troubleshooting

### DNS Not Configured
Make sure DNS records are set:
- `app.tri2directaitravel.com.au` → A record → 76.13.195.67
- `chat.tri2directaitravel.com.au` → A record → 76.13.195.67

### Certificate Renewal Issues
```bash
# Check certbot logs
docker compose -f docker-compose-prod.yml logs certbot

# Manual renewal
docker compose -f docker-compose-prod.yml run --rm certbot renew
```

### Nginx Configuration Error
```bash
# Test config
docker compose -f docker-compose-prod.yml exec nginx nginx -t

# Reload
docker compose -f docker-compose-prod.yml exec nginx nginx -s reload
```

## Security Features Enabled

✅ HTTPS with TLS 1.2 & 1.3
✅ HSTS preloading
✅ Security headers (X-Frame-Options, CSP, etc.)
✅ Rate limiting (10 req/s for web, 100 req/s for API)
✅ Automatic certificate renewal
✅ Gzip compression
✅ WebSocket support

