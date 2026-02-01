# EC2 Deployment Guide

This guide walks you through deploying the Calling Agent to AWS EC2 and connecting it to your Hostinger website.

## Architecture Overview

```
┌─────────────────────┐         ┌─────────────────────┐
│   Hostinger         │         │   AWS EC2           │
│   (reapdat.com)     │  API    │   (api.reapdat.com) │
│                     │ ◄─────► │                     │
│   Next.js Website   │  HTTPS  │   FastAPI Backend   │
│   - Voice AI Page   │         │   - Calling Agent   │
│   - Dashboard       │         │   - Turso DB        │
└─────────────────────┘         └─────────────────────┘
                                         │
                                         ▼
                                ┌─────────────────────┐
                                │   External Services │
                                │   - Ultravox AI     │
                                │   - Twilio          │
                                │   - OpenAI          │
                                └─────────────────────┘
```

## Prerequisites

- AWS Account with EC2 access
- Domain name (for SSL)
- SSH key pair for EC2
- Git repository access

## Step 1: Launch EC2 Instance

### Recommended Instance Type
- **t3.small** or **t3.medium** for production
- **t3.micro** for testing (free tier eligible)

### Launch Configuration
1. Go to AWS Console → EC2 → Launch Instance
2. Choose **Ubuntu Server 22.04 LTS**
3. Select instance type (t3.small recommended)
4. Configure storage: **20 GB gp3**
5. Security Group rules:
   - SSH (22) - Your IP only
   - HTTP (80) - Anywhere
   - HTTPS (443) - Anywhere
   - Custom TCP (8000) - Anywhere (optional, for testing)

### Security Group Example
```
Inbound Rules:
- SSH (22)     : Your IP
- HTTP (80)    : 0.0.0.0/0
- HTTPS (443)  : 0.0.0.0/0
- TCP (8000)   : 0.0.0.0/0  (remove in production)
```

## Step 2: Connect and Setup EC2

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>

# Download and run setup script
curl -O https://raw.githubusercontent.com/gvkmdkra/ai_agents_poc/calling_agent_by_claude_version1/calling_agent/scripts/ec2-setup.sh
chmod +x ec2-setup.sh
./ec2-setup.sh

# Log out and log back in (for docker group)
exit
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

## Step 3: Deploy the Application

```bash
# Clone repository
cd /opt/calling-agent
git clone -b calling_agent_by_claude_version1 https://github.com/gvkmdkra/ai_agents_poc.git .

# Navigate to calling agent
cd calling_agent

# Create .env file
cp .env.example .env
nano .env  # Edit with your credentials
```

### Required .env Configuration
```bash
# API Keys (REQUIRED)
OPENAI_API_KEY=your-openai-key
ULTRAVOX_API_KEY=your-ultravox-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Database
DATABASE_TYPE=turso
TURSO_DB_URL=your-turso-url
TURSO_DB_AUTH_TOKEN=your-turso-token

# IMPORTANT: Update this to your domain
API_BASE_URL=https://api.reapdat.com

# Production settings
ENVIRONMENT=production
DEBUG=false
```

### Deploy
```bash
# Run deployment script
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Verify it's running
curl http://localhost:8000/health
```

## Step 4: Configure Domain & SSL

### Option A: Using Subdomain (Recommended)

1. In your domain registrar (or Hostinger DNS), add an A record:
   ```
   Type: A
   Name: api
   Value: <EC2-PUBLIC-IP>
   TTL: 300
   ```

2. Wait for DNS propagation (5-30 minutes)

3. Run SSL setup:
   ```bash
   chmod +x scripts/ssl-setup.sh
   ./scripts/ssl-setup.sh api.reapdat.com
   ```

### Option B: Using Elastic IP

1. Allocate Elastic IP in AWS Console
2. Associate with your EC2 instance
3. Update DNS A record with Elastic IP
4. Run SSL setup

## Step 5: Verify Deployment

```bash
# Check containers are running
docker-compose ps

# View logs
docker-compose logs -f

# Test API
curl https://api.reapdat.com/health
curl https://api.reapdat.com/docs
```

## Step 6: Connect Hostinger Website

Update your Next.js website to use the EC2 backend:

### In your Hostinger website code:

```typescript
// lib/api.ts or similar
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.reapdat.com';

export async function initiateCall(phoneNumber: string, systemPrompt?: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/calls/initiate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
    },
    body: JSON.stringify({
      phone_number: phoneNumber,
      system_prompt: systemPrompt,
    }),
  });
  return response.json();
}
```

### Environment Variables for Hostinger
Add to your Hostinger deployment:
```
NEXT_PUBLIC_API_URL=https://api.reapdat.com
NEXT_PUBLIC_API_KEY=your-tenant-api-key
```

## Maintenance Commands

```bash
# View logs
docker-compose logs -f calling-agent

# Restart application
docker-compose restart

# Update to latest code
cd /opt/calling-agent/calling_agent
git pull origin calling_agent_by_claude_version1
docker-compose build --no-cache
docker-compose up -d

# Backup call records
docker cp calling-agent:/app/call_records.json ./backup_$(date +%Y%m%d).json
```

## Monitoring

### Health Check Endpoint
```
GET https://api.reapdat.com/health
```

### CloudWatch (Optional)
1. Install CloudWatch agent on EC2
2. Configure to collect Docker logs
3. Set up alarms for:
   - CPU > 80%
   - Memory > 80%
   - Health check failures

## Troubleshooting

### Application won't start
```bash
# Check Docker logs
docker-compose logs --tail=100 calling-agent

# Check if port is in use
sudo netstat -tlnp | grep 8000

# Restart Docker
sudo systemctl restart docker
docker-compose up -d
```

### SSL Certificate Issues
```bash
# Renew certificate manually
sudo certbot renew

# Copy new certificates
sudo cp /etc/letsencrypt/live/api.reapdat.com/*.pem /opt/calling-agent/calling_agent/nginx/ssl/

# Restart nginx
docker-compose restart nginx
```

### Database Connection Issues
```bash
# Test Turso connection
docker-compose exec calling-agent python -c "
from app.db import get_repository
import asyncio
async def test():
    repo = get_repository()
    connected = await repo.initialize()
    print(f'Database connected: {connected}')
asyncio.run(test())
"
```

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| t3.small EC2 | ~$15 |
| Elastic IP | ~$3 (if unused) |
| Data Transfer | ~$5-10 |
| **Total** | **~$20-25/month** |

Free tier eligible (t3.micro) for first 12 months.

## Security Best Practices

1. **Never commit .env files** to git
2. **Use IAM roles** instead of access keys when possible
3. **Enable automatic security updates**: `sudo apt-get install unattended-upgrades`
4. **Regularly rotate API keys**
5. **Monitor for unauthorized access** via CloudTrail
6. **Use VPC** for network isolation in production
