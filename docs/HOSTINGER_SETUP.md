# Hostinger Domain Configuration Guide

This guide explains how to configure your Hostinger domain to point to the Unified AI Agent deployed on EC2.

## Prerequisites

- Access to Hostinger DNS management for reapdat.com
- EC2 instance running at IP: 15.156.116.91
- Unified Agent deployed and running

## DNS Configuration

### Step 1: Access Hostinger DNS Settings

1. Log in to your Hostinger account
2. Go to **Domains** > **reapdat.com** > **DNS / Nameservers**
3. Click on **Manage DNS Records**

### Step 2: Add A Records

Add the following DNS records:

| Type | Name | Points To | TTL |
|------|------|-----------|-----|
| A | api | 15.156.116.91 | 14400 |
| A | app | 15.156.116.91 | 14400 |

### Step 3: Verify DNS Propagation

DNS changes can take up to 24-48 hours to propagate. You can check propagation status at:
- https://www.whatsmydns.net/
- https://dnschecker.org/

Test with:
```bash
nslookup api.reapdat.com
nslookup app.reapdat.com
```

## SSL Certificate Setup

After DNS propagation (verify with `nslookup api.reapdat.com`), you have two options:

### Option 1: Use GitHub Actions Workflow (Recommended)
1. Go to the repository's **Actions** tab
2. Select **Setup SSL Certificates** workflow
3. Click **Run workflow**
4. This will automatically obtain certificates and configure HTTPS

### Option 2: Manual Setup
SSH into the EC2 instance and run:

```bash
sudo certbot --nginx -d api.reapdat.com -d app.reapdat.com --non-interactive --agree-tos --email admin@reapdat.com --redirect
```

This will automatically configure HTTPS for both domains and redirect HTTP to HTTPS.

## Nginx Configuration

The deployment workflow automatically configures Nginx with:

- `api.reapdat.com` -> Backend API (port 8000)
- `app.reapdat.com` -> Dashboard (port 3000)

Manual configuration (if needed):

```bash
sudo nano /etc/nginx/sites-available/unified-agent
```

```nginx
server {
    listen 80;
    server_name api.reapdat.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

server {
    listen 80;
    server_name app.reapdat.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable the site:
```bash
sudo ln -sf /etc/nginx/sites-available/unified-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Security Group Configuration

Ensure EC2 security group allows:

| Port | Protocol | Source | Description |
|------|----------|--------|-------------|
| 80 | TCP | 0.0.0.0/0 | HTTP |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 8000 | TCP | 0.0.0.0/0 | API (optional, can remove after Nginx setup) |
| 3000 | TCP | 0.0.0.0/0 | Dashboard (optional, can remove after Nginx setup) |

## Final URLs

After complete setup:

| Service | URL |
|---------|-----|
| API Documentation | https://api.reapdat.com/docs |
| Dashboard | https://app.reapdat.com |
| Health Check | https://api.reapdat.com/health |

## Troubleshooting

### DNS Not Resolving
- Wait 24-48 hours for full propagation
- Clear local DNS cache: `ipconfig /flushdns` (Windows) or `sudo dscacheutil -flushcache` (Mac)

### SSL Certificate Issues
```bash
sudo certbot certificates
sudo certbot renew --dry-run
```

### Nginx Issues
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### Docker Issues
```bash
cd /home/ubuntu/poc/agents/unified_agent
sudo docker-compose logs --tail=100
sudo docker-compose ps
```
