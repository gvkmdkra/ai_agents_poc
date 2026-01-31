# AWS EC2 Deployment Guide

## AI Voice Agent - Production Deployment on AWS

This guide covers deploying the AI Voice Agent system on AWS EC2 with production-ready infrastructure.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [AWS Services Used](#aws-services-used)
3. [Infrastructure Setup](#infrastructure-setup)
4. [EC2 Instance Setup](#ec2-instance-setup)
5. [Database Setup (RDS)](#database-setup-rds)
6. [Redis Setup (ElastiCache)](#redis-setup-elasticache)
7. [Load Balancer (ALB)](#load-balancer-alb)
8. [SSL/TLS Configuration](#ssltls-configuration)
9. [Domain & DNS Setup](#domain--dns-setup)
10. [Deployment Scripts](#deployment-scripts)
11. [Docker Deployment](#docker-deployment)
12. [Environment Configuration](#environment-configuration)
13. [Monitoring & Logging](#monitoring--logging)
14. [Auto Scaling](#auto-scaling)
15. [Security Best Practices](#security-best-practices)
16. [Troubleshooting](#troubleshooting)

---

## 1. Architecture Overview

```
                                    ┌─────────────────┐
                                    │   Route 53      │
                                    │   (DNS)         │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  CloudFront     │
                                    │  (CDN + WAF)    │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  Application    │
                                    │  Load Balancer  │
                                    │  (HTTPS:443)    │
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
    ┌─────────▼─────────┐        ┌──────────▼──────────┐        ┌─────────▼─────────┐
    │   EC2 Instance    │        │   EC2 Instance      │        │   EC2 Instance    │
    │   (App Server)    │        │   (App Server)      │        │   (Worker)        │
    │   t3.medium       │        │   t3.medium         │        │   t3.small        │
    │                   │        │                     │        │                   │
    │ ┌───────────────┐ │        │ ┌───────────────┐   │        │ ┌───────────────┐ │
    │ │ Docker        │ │        │ │ Docker        │   │        │ │ Docker        │ │
    │ │ - API Server  │ │        │ │ - API Server  │   │        │ │ - Celery      │ │
    │ │ - LangGraph   │ │        │ │ - LangGraph   │   │        │ │ - Beat        │ │
    │ │ - WebSocket   │ │        │ │ - WebSocket   │   │        │ │               │ │
    │ └───────────────┘ │        │ └───────────────┘   │        │ └───────────────┘ │
    └─────────┬─────────┘        └──────────┬──────────┘        └─────────┬─────────┘
              │                              │                              │
              └──────────────────────────────┼──────────────────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
    ┌─────────▼─────────┐        ┌──────────▼──────────┐        ┌─────────▼─────────┐
    │   RDS PostgreSQL  │        │   ElastiCache       │        │   S3 Bucket       │
    │   (db.t3.medium)  │        │   Redis Cluster     │        │   (Recordings)    │
    │                   │        │   (cache.t3.micro)  │        │                   │
    │   Multi-AZ        │        │                     │        │   - Call records  │
    │   Automated       │        │   - Session cache   │        │   - Transcripts   │
    │   backups         │        │   - Task queue      │        │   - Voice files   │
    └───────────────────┘        └─────────────────────┘        └───────────────────┘
```

---

## 2. AWS Services Used

| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| **EC2** | Application servers | ~$60-120/month |
| **RDS PostgreSQL** | Primary database | ~$50-100/month |
| **ElastiCache Redis** | Caching & queues | ~$25-50/month |
| **ALB** | Load balancing | ~$20-30/month |
| **S3** | File storage | ~$5-20/month |
| **Route 53** | DNS management | ~$1/month |
| **ACM** | SSL certificates | Free |
| **CloudWatch** | Monitoring & logs | ~$10-30/month |
| **VPC** | Network isolation | Free |
| **NAT Gateway** | Outbound internet | ~$35/month |

**Estimated Total:** $200-400/month (varies by traffic)

---

## 3. Infrastructure Setup

### 3.1 VPC Configuration

```bash
# Create VPC with CIDR block
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=voice-agent-vpc}]'

# Create subnets
# Public subnets (for ALB, NAT Gateway)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 --availability-zone us-east-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-1a}]'
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 --availability-zone us-east-1b --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-1b}]'

# Private subnets (for EC2, RDS, ElastiCache)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.10.0/24 --availability-zone us-east-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-1a}]'
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.11.0/24 --availability-zone us-east-1b --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-1b}]'
```

### 3.2 Security Groups

```bash
# ALB Security Group (allows HTTPS from internet)
aws ec2 create-security-group \
  --group-name voice-agent-alb-sg \
  --description "ALB Security Group" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-alb-xxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id sg-alb-xxx \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

# EC2 Security Group (allows traffic from ALB)
aws ec2 create-security-group \
  --group-name voice-agent-ec2-sg \
  --description "EC2 Security Group" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-ec2-xxx \
  --protocol tcp \
  --port 8000 \
  --source-group sg-alb-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-ec2-xxx \
  --protocol tcp \
  --port 9000 \
  --source-group sg-alb-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-ec2-xxx \
  --protocol tcp \
  --port 8080 \
  --source-group sg-alb-xxx

# Allow SSH from your IP (for management)
aws ec2 authorize-security-group-ingress \
  --group-id sg-ec2-xxx \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# RDS Security Group (allows PostgreSQL from EC2)
aws ec2 create-security-group \
  --group-name voice-agent-rds-sg \
  --description "RDS Security Group" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-rds-xxx \
  --protocol tcp \
  --port 5432 \
  --source-group sg-ec2-xxx

# Redis Security Group (allows Redis from EC2)
aws ec2 create-security-group \
  --group-name voice-agent-redis-sg \
  --description "Redis Security Group" \
  --vpc-id vpc-xxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-redis-xxx \
  --protocol tcp \
  --port 6379 \
  --source-group sg-ec2-xxx
```

---

## 4. EC2 Instance Setup

### 4.1 Launch EC2 Instance

**Recommended Instance Types:**

| Workload | Instance Type | vCPU | RAM | Purpose |
|----------|--------------|------|-----|---------|
| Small (< 100 calls/day) | t3.medium | 2 | 4GB | All-in-one |
| Medium (100-500 calls/day) | t3.large | 2 | 8GB | App servers |
| Large (500+ calls/day) | t3.xlarge | 4 | 16GB | High traffic |
| Worker | t3.small | 2 | 2GB | Background tasks |

```bash
# Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --security-group-ids sg-ec2-xxx \
  --subnet-id subnet-private-xxx \
  --iam-instance-profile Name=voice-agent-ec2-role \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":50,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=voice-agent-app-1}]' \
  --user-data file://ec2-user-data.sh
```

### 4.2 EC2 User Data Script (ec2-user-data.sh)

```bash
#!/bin/bash
set -e

# Update system
yum update -y

# Install Docker
amazon-linux-extras install docker -y
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Install CloudWatch agent
yum install amazon-cloudwatch-agent -y

# Install git
yum install git -y

# Create app directory
mkdir -p /opt/voice-agent
chown ec2-user:ec2-user /opt/voice-agent

# Install SSM agent (for remote management)
yum install amazon-ssm-agent -y
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

echo "EC2 setup complete!"
```

### 4.3 IAM Role for EC2

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::voice-agent-recordings/*",
        "arn:aws:s3:::voice-agent-recordings"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:voice-agent/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/voice-agent/*"
    }
  ]
}
```

---

## 5. Database Setup (RDS)

### 5.1 Create RDS PostgreSQL Instance

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name voice-agent-db-subnet \
  --db-subnet-group-description "Voice Agent DB Subnets" \
  --subnet-ids subnet-private-1a subnet-private-1b

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier voice-agent-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username voiceagent_admin \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 50 \
  --storage-type gp3 \
  --vpc-security-group-ids sg-rds-xxx \
  --db-subnet-group-name voice-agent-db-subnet \
  --backup-retention-period 7 \
  --multi-az \
  --storage-encrypted \
  --deletion-protection \
  --tags Key=Name,Value=voice-agent-db
```

### 5.2 Database Initialization

```bash
# Connect to RDS and run migrations
psql -h voice-agent-db.xxx.us-east-1.rds.amazonaws.com \
     -U voiceagent_admin \
     -d postgres \
     -f src/core/database/migrations/004_voice_agent_tables.sql
```

---

## 6. Redis Setup (ElastiCache)

```bash
# Create ElastiCache subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name voice-agent-redis-subnet \
  --cache-subnet-group-description "Voice Agent Redis Subnets" \
  --subnet-ids subnet-private-1a subnet-private-1b

# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id voice-agent-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --cache-subnet-group-name voice-agent-redis-subnet \
  --security-group-ids sg-redis-xxx \
  --tags Key=Name,Value=voice-agent-redis
```

---

## 7. Load Balancer (ALB)

### 7.1 Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name voice-agent-alb \
  --subnets subnet-public-1a subnet-public-1b \
  --security-groups sg-alb-xxx \
  --scheme internet-facing \
  --type application \
  --tags Key=Name,Value=voice-agent-alb

# Create target groups
aws elbv2 create-target-group \
  --name voice-agent-api-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type instance \
  --health-check-path /health \
  --health-check-interval-seconds 30

aws elbv2 create-target-group \
  --name voice-agent-ws-tg \
  --protocol HTTP \
  --port 8080 \
  --vpc-id vpc-xxx \
  --target-type instance \
  --health-check-path /health \
  --health-check-interval-seconds 30

# Create HTTPS listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:xxx \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:xxx \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:xxx:targetgroup/voice-agent-api-tg

# Create listener rules for WebSocket
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:xxx \
  --priority 10 \
  --conditions Field=path-pattern,Values=/media-stream/* \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:xxx:targetgroup/voice-agent-ws-tg
```

---

## 8. SSL/TLS Configuration

### 8.1 Request SSL Certificate (ACM)

```bash
# Request certificate
aws acm request-certificate \
  --domain-name voice.yourdomain.com \
  --validation-method DNS \
  --subject-alternative-names "*.voice.yourdomain.com"

# After DNS validation, certificate will be issued automatically
```

---

## 9. Domain & DNS Setup

### 9.1 Route 53 Configuration

```bash
# Create hosted zone (if not exists)
aws route53 create-hosted-zone \
  --name yourdomain.com \
  --caller-reference $(date +%s)

# Create A record pointing to ALB
aws route53 change-resource-record-sets \
  --hosted-zone-id ZXXXXX \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "voice.yourdomain.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "voice-agent-alb-xxx.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

---

## 10. Deployment Scripts

### 10.1 Deploy Script (deploy.sh)

```bash
#!/bin/bash
set -e

# Configuration
APP_DIR="/opt/voice-agent"
REPO_URL="https://github.com/gvkmdkra/ai_agents_poc.git"
BRANCH="calling_agent_chat_agent_end_to_end"

echo "🚀 Starting deployment..."

# Navigate to app directory
cd $APP_DIR

# Pull latest code
if [ -d ".git" ]; then
    echo "📥 Pulling latest changes..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo "📦 Cloning repository..."
    git clone -b $BRANCH $REPO_URL .
fi

# Load environment variables from AWS Secrets Manager
echo "🔐 Loading secrets..."
export $(aws secretsmanager get-secret-value \
    --secret-id voice-agent/production \
    --query SecretString \
    --output text | jq -r 'to_entries | .[] | "\(.key)=\(.value)"')

# Build and deploy with Docker Compose
echo "🐳 Building containers..."
docker-compose -f docker-compose.prod.yml build

echo "🔄 Deploying containers..."
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
echo "📊 Running migrations..."
docker-compose -f docker-compose.prod.yml exec -T api-server \
    python -c "from src.core.database import run_migrations; run_migrations()"

# Health check
echo "❤️ Running health check..."
sleep 10
curl -f http://localhost:8000/health || exit 1

echo "✅ Deployment complete!"
```

### 10.2 Rollback Script (rollback.sh)

```bash
#!/bin/bash
set -e

APP_DIR="/opt/voice-agent"
PREVIOUS_COMMIT=$1

if [ -z "$PREVIOUS_COMMIT" ]; then
    echo "Usage: ./rollback.sh <commit-hash>"
    exit 1
fi

echo "🔙 Rolling back to $PREVIOUS_COMMIT..."

cd $APP_DIR

# Checkout previous commit
git checkout $PREVIOUS_COMMIT

# Rebuild and redeploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

echo "✅ Rollback complete!"
```

---

## 11. Docker Deployment

### 11.1 Production Docker Compose (docker-compose.prod.yml)

```yaml
version: '3.8'

services:
  api-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: voice-agent-api
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - ULTRAVOX_API_KEY=${ULTRAVOX_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ODOO_URL=${ODOO_URL}
      - ODOO_API_KEY=${ODOO_API_KEY}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
      - AWS_REGION=${AWS_REGION}
      - S3_BUCKET=${S3_BUCKET}
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: /voice-agent/api-server
        awslogs-region: us-east-1
        awslogs-stream-prefix: api
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G

  langgraph-server:
    build:
      context: .
      dockerfile: Dockerfile.langgraph
    container_name: voice-agent-langgraph
    restart: always
    ports:
      - "9000:9000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: /voice-agent/langgraph
        awslogs-region: us-east-1
        awslogs-stream-prefix: langgraph

  websocket-gateway:
    build:
      context: .
      dockerfile: Dockerfile.websocket
    container_name: voice-agent-websocket
    restart: always
    ports:
      - "8080:8080"
    environment:
      - ULTRAVOX_API_KEY=${ULTRAVOX_API_KEY}
      - REDIS_URL=${REDIS_URL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: /voice-agent/websocket
        awslogs-region: us-east-1
        awslogs-stream-prefix: ws

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: voice-agent-worker
    restart: always
    command: celery -A src.voice_agent.tasks worker -l info -c 4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
    logging:
      driver: awslogs
      options:
        awslogs-group: /voice-agent/worker
        awslogs-region: us-east-1
        awslogs-stream-prefix: worker
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: voice-agent-beat
    restart: always
    command: celery -A src.voice_agent.tasks beat -l info
    environment:
      - REDIS_URL=${REDIS_URL}
    logging:
      driver: awslogs
      options:
        awslogs-group: /voice-agent/beat
        awslogs-region: us-east-1
        awslogs-stream-prefix: beat

networks:
  default:
    driver: bridge
```

### 11.2 Production Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 12. Environment Configuration

### 12.1 Store Secrets in AWS Secrets Manager

```bash
# Create secret
aws secretsmanager create-secret \
    --name voice-agent/production \
    --description "Voice Agent Production Secrets" \
    --secret-string '{
        "DATABASE_URL": "postgresql://user:pass@voice-agent-db.xxx.rds.amazonaws.com:5432/voiceagent",
        "REDIS_URL": "redis://voice-agent-redis.xxx.cache.amazonaws.com:6379",
        "TWILIO_ACCOUNT_SID": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "TWILIO_AUTH_TOKEN": "your_auth_token",
        "ULTRAVOX_API_KEY": "your_ultravox_key",
        "OPENAI_API_KEY": "sk-xxxxxxxxxxxxxxxx",
        "ODOO_URL": "https://your-odoo.com",
        "ODOO_API_KEY": "your_odoo_key",
        "SENDGRID_API_KEY": "SG.xxxxxxxx",
        "S3_BUCKET": "voice-agent-recordings",
        "AWS_REGION": "us-east-1"
    }'
```

### 12.2 Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | Yes |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | Yes |
| `ULTRAVOX_API_KEY` | Ultravox API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ODOO_URL` | Odoo instance URL | Yes |
| `ODOO_API_KEY` | Odoo API key | Yes |
| `SENDGRID_API_KEY` | SendGrid API key | For email |
| `S3_BUCKET` | S3 bucket for recordings | Yes |
| `AWS_REGION` | AWS region | Yes |
| `LOG_LEVEL` | Logging level | No (default: INFO) |

---

## 13. Monitoring & Logging

### 13.1 CloudWatch Dashboard

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
    --dashboard-name VoiceAgentDashboard \
    --dashboard-body file://cloudwatch-dashboard.json
```

### 13.2 CloudWatch Alarms

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
    --alarm-name voice-agent-high-cpu \
    --alarm-description "High CPU on Voice Agent" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions arn:aws:sns:us-east-1:xxx:alerts

# API error rate alarm
aws cloudwatch put-metric-alarm \
    --alarm-name voice-agent-api-errors \
    --alarm-description "High API error rate" \
    --metric-name 5XXError \
    --namespace AWS/ApplicationELB \
    --statistic Sum \
    --period 60 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions arn:aws:sns:us-east-1:xxx:alerts
```

### 13.3 Log Groups

```bash
# Create log groups
aws logs create-log-group --log-group-name /voice-agent/api-server
aws logs create-log-group --log-group-name /voice-agent/langgraph
aws logs create-log-group --log-group-name /voice-agent/websocket
aws logs create-log-group --log-group-name /voice-agent/worker
aws logs create-log-group --log-group-name /voice-agent/beat

# Set retention
aws logs put-retention-policy --log-group-name /voice-agent/api-server --retention-in-days 30
```

---

## 14. Auto Scaling

### 14.1 Create Launch Template

```bash
aws ec2 create-launch-template \
    --launch-template-name voice-agent-template \
    --version-description "Voice Agent v1" \
    --launch-template-data '{
        "ImageId": "ami-xxx",
        "InstanceType": "t3.medium",
        "KeyName": "your-key-pair",
        "SecurityGroupIds": ["sg-ec2-xxx"],
        "IamInstanceProfile": {"Name": "voice-agent-ec2-role"},
        "UserData": "base64-encoded-user-data",
        "BlockDeviceMappings": [{
            "DeviceName": "/dev/xvda",
            "Ebs": {"VolumeSize": 50, "VolumeType": "gp3"}
        }]
    }'
```

### 14.2 Create Auto Scaling Group

```bash
aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name voice-agent-asg \
    --launch-template LaunchTemplateName=voice-agent-template,Version=1 \
    --min-size 2 \
    --max-size 6 \
    --desired-capacity 2 \
    --vpc-zone-identifier "subnet-private-1a,subnet-private-1b" \
    --target-group-arns arn:aws:elasticloadbalancing:xxx:targetgroup/voice-agent-api-tg \
    --health-check-type ELB \
    --health-check-grace-period 300

# Create scaling policies
aws autoscaling put-scaling-policy \
    --auto-scaling-group-name voice-agent-asg \
    --policy-name scale-out \
    --policy-type TargetTrackingScaling \
    --target-tracking-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ASGAverageCPUUtilization"
        }
    }'
```

---

## 15. Security Best Practices

### 15.1 Security Checklist

- [ ] All secrets stored in AWS Secrets Manager
- [ ] RDS encryption at rest enabled
- [ ] RDS Multi-AZ for high availability
- [ ] VPC with private subnets for EC2/RDS/Redis
- [ ] Security groups with minimal access
- [ ] SSL/TLS for all public endpoints
- [ ] WAF rules for API protection
- [ ] IAM roles with least privilege
- [ ] CloudTrail enabled for audit logs
- [ ] Regular security patching

### 15.2 WAF Rules (Optional)

```bash
# Create WAF Web ACL
aws wafv2 create-web-acl \
    --name voice-agent-waf \
    --scope REGIONAL \
    --default-action Allow={} \
    --rules file://waf-rules.json \
    --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=voice-agent-waf
```

---

## 16. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Container won't start | Check `docker logs <container>` for errors |
| Database connection failed | Verify security group allows EC2 to RDS |
| Redis connection failed | Check ElastiCache security group |
| ALB health check failing | Ensure `/health` endpoint returns 200 |
| High latency | Check CloudWatch metrics, consider scaling |
| Twilio webhooks not working | Verify ALB DNS is correct in Twilio console |

### Useful Commands

```bash
# View container logs
docker-compose -f docker-compose.prod.yml logs -f api-server

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Check container status
docker-compose -f docker-compose.prod.yml ps

# Run database migrations manually
docker-compose -f docker-compose.prod.yml exec api-server python -c "from src.core.database import run_migrations; run_migrations()"

# Connect to container shell
docker-compose -f docker-compose.prod.yml exec api-server /bin/bash

# Check application health
curl http://localhost:8000/health
```

---

## Quick Start Summary

```bash
# 1. Launch EC2 instance with user data script
# 2. SSH into instance
ssh -i your-key.pem ec2-user@your-instance-ip

# 3. Clone repository
cd /opt/voice-agent
git clone -b calling_agent_chat_agent_end_to_end https://github.com/gvkmdkra/ai_agents_poc.git .

# 4. Configure environment
# Store secrets in AWS Secrets Manager first

# 5. Deploy
./deploy.sh

# 6. Configure Twilio webhooks to point to your ALB
# https://voice.yourdomain.com/webhook/voice/answer
```

Your AI Voice Agent is now running on AWS EC2!
