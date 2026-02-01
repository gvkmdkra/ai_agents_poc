#!/bin/bash
# Deployment Script for Calling Agent
# Run this on EC2 after initial setup

set -e

APP_DIR="/opt/calling-agent"
REPO_URL="https://github.com/gvkmdkra/ai_agents_poc.git"
BRANCH="calling_agent_by_claude_version1"

echo "=========================================="
echo "Deploying Calling Agent"
echo "=========================================="

cd $APP_DIR

# Pull latest code
if [ -d ".git" ]; then
    echo "Pulling latest changes..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo "Cloning repository..."
    git clone -b $BRANCH $REPO_URL .
fi

# Navigate to calling_agent directory
cd calling_agent

# Check for .env file
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Build and deploy
echo "Building Docker image..."
docker-compose build --no-cache

echo "Stopping existing containers..."
docker-compose down || true

echo "Starting new containers..."
docker-compose up -d

# Wait for health check
echo "Waiting for application to start..."
sleep 10

# Check health
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "=========================================="
    echo "Deployment Successful!"
    echo "=========================================="
    echo "Application is running at http://localhost:8000"
    echo ""
    echo "View logs: docker-compose logs -f"
else
    echo "WARNING: Health check failed. Check logs:"
    docker-compose logs --tail=50
fi
