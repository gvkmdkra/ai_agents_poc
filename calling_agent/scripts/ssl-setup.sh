#!/bin/bash
# SSL Setup Script using Let's Encrypt
# Run after deploy.sh

set -e

if [ -z "$1" ]; then
    echo "Usage: ./ssl-setup.sh your-domain.com"
    exit 1
fi

DOMAIN=$1
APP_DIR="/opt/calling-agent/calling_agent"

echo "=========================================="
echo "Setting up SSL for $DOMAIN"
echo "=========================================="

# Stop any running containers
cd $APP_DIR
docker-compose down || true

# Get SSL certificate
echo "Obtaining SSL certificate..."
sudo certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

# Create SSL directory
mkdir -p $APP_DIR/nginx/ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_DIR/nginx/ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_DIR/nginx/ssl/
sudo chown -R $USER:$USER $APP_DIR/nginx/ssl/

# Update .env with domain
sed -i "s|API_BASE_URL=.*|API_BASE_URL=https://$DOMAIN|g" $APP_DIR/.env

# Start with nginx
echo "Starting application with SSL..."
docker-compose -f docker-compose.prod.yml up -d

# Setup auto-renewal
echo "Setting up certificate auto-renewal..."
(crontab -l 2>/dev/null; echo "0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/*.pem $APP_DIR/nginx/ssl/ && docker-compose -f $APP_DIR/docker-compose.prod.yml restart nginx") | crontab -

echo "=========================================="
echo "SSL Setup Complete!"
echo "=========================================="
echo "Your API is now available at: https://$DOMAIN"
