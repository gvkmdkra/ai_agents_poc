#!/bin/bash
# EC2 Initial Setup Script for Calling Agent
# Run this script on a fresh Ubuntu 22.04 EC2 instance

set -e

echo "=========================================="
echo "Calling Agent - EC2 Setup Script"
echo "=========================================="

# Update system
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
echo "Installing Docker..."
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add current user to docker group
sudo usermod -aG docker $USER

# Install Git
echo "Installing Git..."
sudo apt-get install -y git

# Create app directory
echo "Creating application directory..."
sudo mkdir -p /opt/calling-agent
sudo chown $USER:$USER /opt/calling-agent

# Install Nginx for SSL termination (optional, can use docker nginx instead)
# sudo apt-get install -y nginx

# Configure firewall
echo "Configuring firewall..."
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # Direct API access (optional, remove in production)
sudo ufw --force enable

# Install certbot for SSL
echo "Installing Certbot..."
sudo apt-get install -y certbot

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Log out and log back in (for docker group)"
echo "2. Clone your repository to /opt/calling-agent"
echo "3. Copy your .env file"
echo "4. Run: docker-compose up -d"
echo ""
echo "For SSL setup, run:"
echo "  sudo certbot certonly --standalone -d your-domain.com"
echo ""
