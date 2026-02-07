# Unified Agent Platform v1.0

> **Enterprise-Grade AI Agent Platform** - Combining Voice, Chat, Workflows & Analytics

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 What is Unified Agent Platform?

**Unified Agent Platform** is a production-ready, enterprise-grade AI agent system that consolidates:
- 📞 **Voice Calling** (Twilio + Ultravox)
- 💬 **Chat & RAG** (Pinecone + OpenAI/Gemini)
- 🔄 **Workflow Automation** (n8n integration)
- 📊 **Analytics & Reporting** (Real-time dashboards)
- 🏢 **Multi-Tenancy** (Complete isolation & white-label)
- 🔐 **Enterprise Security** (OAuth2, RBAC, encryption)

**Industry Standard Architecture** inspired by Databricks, Snowflake, and AWS Well-Architected Framework.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED AGENT PLATFORM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Next.js    │  │   Mobile     │  │ Chat Widget  │         │
│  │   Frontend   │  │   App        │  │   (Embedd)   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         └──────────────────┼──────────────────┘                 │
│                            │                                     │
│         ┌──────────────────▼───────────────────┐               │
│         │      API Gateway (FastAPI)           │               │
│         │  • Auth • Rate Limit • Routing       │               │
│         └──────────────────┬───────────────────┘               │
│                            │                                     │
│         ┌──────────────────┴───────────────────┐               │
│         │       SERVICE MESH LAYER             │               │
│         │  ┌────────┐  ┌────────┐  ┌────────┐ │               │
│         │  │ Voice  │  │  Chat  │  │Workflow│ │               │
│         │  │Service │  │Service │  │Service │ │               │
│         │  └────────┘  └────────┘  └────────┘ │               │
│         │  ┌────────┐  ┌────────┐  ┌────────┐ │               │
│         │  │Tenant  │  │Analytics│  │ Plugin │ │               │
│         │  │Service │  │Service  │  │ System │ │               │
│         │  └────────┘  └────────┘  └────────┘ │               │
│         └──────────────────┬───────────────────┘               │
│                            │                                     │
│         ┌──────────────────▼───────────────────┐               │
│         │        DATA ACCESS LAYER             │               │
│         │  • PostgreSQL  • Redis  • Pinecone   │               │
│         └──────────────────────────────────────┘               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for frontend)
- API Keys (OpenAI, Twilio, Ultravox, Pinecone)

### 1. Clone and Setup
```bash
cd unified_agent_1

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Start with Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Access Services
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **n8n Workflows**: http://localhost:5678
- **Grafana**: http://localhost:3001

---

## 📁 Project Structure

```
unified_agent_1/
├── backend/                    # Backend services
│   ├── api/                   # API gateway & routes
│   │   ├── v1/               # API version 1
│   │   │   ├── voice.py      # Voice endpoints
│   │   │   ├── chat.py       # Chat endpoints
│   │   │   ├── workflow.py   # Workflow endpoints
│   │   │   ├── tenant.py     # Tenant management
│   │   │   └── analytics.py  # Analytics endpoints
│   │   ├── middleware/       # Auth, rate limiting, CORS
│   │   └── gateway.py        # Main API gateway
│   ├── core/                  # Core functionality
│   │   ├── config.py         # Configuration management
│   │   ├── security.py       # Security utilities
│   │   ├── logging.py        # Structured logging
│   │   └── exceptions.py     # Custom exceptions
│   ├── services/              # Business logic layer
│   │   ├── voice/            # Voice service
│   │   │   ├── call_manager.py
│   │   │   ├── twilio_client.py
│   │   │   └── ultravox_client.py
│   │   ├── chat/             # Chat service
│   │   │   ├── conversation_manager.py
│   │   │   ├── rag_engine.py
│   │   │   └── text_to_sql.py
│   │   ├── workflow/         # Workflow service
│   │   │   ├── n8n_client.py
│   │   │   └── workflow_executor.py
│   │   ├── tenant/           # Tenant service
│   │   │   ├── tenant_manager.py
│   │   │   └── auth_provider.py
│   │   └── analytics/        # Analytics service
│   │       ├── metrics_collector.py
│   │       └── report_generator.py
│   ├── models/                # Data models
│   │   ├── tenant.py
│   │   ├── call.py
│   │   ├── conversation.py
│   │   └── workflow.py
│   ├── db/                    # Database layer
│   │   ├── base.py           # Base repository
│   │   ├── repositories/     # Data access objects
│   │   └── migrations/       # Database migrations
│   └── plugins/               # Plugin system
│       ├── llm_providers/    # LLM plugins (OpenAI, Gemini)
│       ├── vector_stores/    # Vector DB plugins
│       └── telephony/        # Phone provider plugins
├── frontend/                  # Frontend applications
│   ├── web/                  # Next.js web app
│   │   ├── app/             # Next.js 13+ app directory
│   │   ├── components/      # React components
│   │   ├── lib/             # Utility functions
│   │   └── public/          # Static assets
│   ├── mobile/               # React Native app
│   └── widget/               # Embeddable chat widget
├── infrastructure/            # Infrastructure as Code
│   ├── docker/               # Docker configurations
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── docker-compose.yml
│   ├── kubernetes/           # K8s manifests
│   │   ├── deployments/
│   │   ├── services/
│   │   └── ingress/
│   └── terraform/            # Cloud infrastructure
│       ├── aws/
│       ├── gcp/
│       └── azure/
├── deployment/                # Deployment configurations
│   ├── dev/                  # Development environment
│   ├── staging/              # Staging environment
│   └── production/           # Production environment
├── docs/                      # Documentation
│   ├── api/                  # API documentation
│   ├── guides/               # User guides
│   └── architecture/         # Architecture docs
├── scripts/                   # Utility scripts
│   ├── setup.sh             # Initial setup
│   ├── migrate.py           # Database migrations
│   └── seed_data.py         # Sample data
├── tests/                     # Test suite
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── e2e/                 # End-to-end tests
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Python project configuration
├── docker-compose.yml        # Local development setup
├── ARCHITECTURE.md          # Architecture documentation
└── README.md                 # This file
```

---

## 🚀 Features

### Voice Service
- ✅ Outbound call initiation
- ✅ Inbound call handling
- ✅ Real-time transcription
- ✅ Call recording and storage
- ✅ Call analytics and reporting
- ✅ IVR (Interactive Voice Response)
- ✅ Call transfer and conferencing

### Chat Service
- ✅ Text-based conversations
- ✅ RAG (Retrieval Augmented Generation)
- ✅ Text-to-SQL queries
- ✅ Multi-LLM support (OpenAI, Gemini, Claude)
- ✅ Context management
- ✅ Lead capture
- ✅ Sentiment analysis

### Workflow Service
- ✅ Visual workflow builder (n8n)
- ✅ Pre-built integrations (200+)
- ✅ Webhook triggers
- ✅ Scheduled tasks
- ✅ Error handling and retries
- ✅ Calendar booking automation
- ✅ CRM integration

### Analytics Service
- ✅ Real-time dashboards
- ✅ Call duration and quality metrics
- ✅ Chat engagement analytics
- ✅ Conversion tracking
- ✅ Custom reports
- ✅ Anomaly detection

### Tenant Management
- ✅ Multi-tenant isolation
- ✅ Self-service onboarding
- ✅ White-label capabilities
- ✅ Custom domain support
- ✅ Usage tracking and billing
- ✅ Audit logging

---

## 📖 API Documentation

### Authentication
All API requests require authentication via API key or JWT token.

**API Key (Header)**:
```bash
X-API-Key: your-api-key-here
```

**JWT Token (Bearer)**:
```bash
Authorization: Bearer your-jwt-token-here
```

### Voice API

#### Initiate Outbound Call
```bash
POST /api/v1/voice/calls/initiate
Content-Type: application/json
X-API-Key: your-api-key

{
  "phone_number": "+14155551234",
  "system_prompt": "You are a helpful assistant",
  "first_speaker": "FIRST_SPEAKER_AGENT",
  "metadata": {
    "campaign": "demo",
    "customer_id": "12345"
  }
}
```

#### Get Call Status
```bash
GET /api/v1/voice/calls/{call_id}
X-API-Key: your-api-key
```

### Chat API

#### Send Message
```bash
POST /api/v1/chat/conversations/{conversation_id}/messages
Content-Type: application/json
X-API-Key: your-api-key

{
  "message": "What services do you offer?",
  "client_name": "John Doe"
}
```

#### Get Conversation History
```bash
GET /api/v1/chat/conversations/{conversation_id}/history
X-API-Key: your-api-key
```

### Workflow API

#### Execute Workflow
```bash
POST /api/v1/workflows/{workflow_id}/execute
Content-Type: application/json
X-API-Key: your-api-key

{
  "input_data": {
    "date": "2026-02-10",
    "service_type": "consultation"
  }
}
```

For complete API documentation, visit: http://localhost:8000/docs

---

## 🔧 Configuration

### Environment Variables

Create `.env` file with the following variables:

```bash
# Application
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key-here
API_BASE_URL=http://localhost:8000

# Database
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/unified_agent

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Twilio
TWILIO_ACCOUNT_SID=ACxxx...
TWILIO_AUTH_TOKEN=xxx...
TWILIO_PHONE_NUMBER=+1234567890

# Ultravox
ULTRAVOX_API_KEY=xxx...
ULTRAVOX_VOICE_ID=xxx...

# Pinecone
PINECONE_API_KEY=xxx...
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=your-index

# n8n
N8N_BASE_URL=http://localhost:5678
```

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/unit -v
```

### Run Integration Tests
```bash
pytest tests/integration -v
```

### Run End-to-End Tests
```bash
pytest tests/e2e -v
```

### Run with Coverage
```bash
pytest --cov=backend --cov-report=html
```

---

## 📦 Deployment

### Docker Deployment
```bash
# Build images
docker-compose -f infrastructure/docker/docker-compose.yml build

# Start services
docker-compose -f infrastructure/docker/docker-compose.yml up -d
```

### Kubernetes Deployment
```bash
# Apply configurations
kubectl apply -f infrastructure/kubernetes/

# Check status
kubectl get pods
kubectl get services
```

### Cloud Deployment (AWS)
```bash
cd infrastructure/terraform/aws

# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Apply changes
terraform apply
```

---

## 🔒 Security

- **Authentication**: OAuth2, JWT, API Keys
- **Authorization**: RBAC (Role-Based Access Control)
- **Encryption**: AES-256 at rest, TLS 1.3 in transit
- **Rate Limiting**: Configurable per tenant
- **CORS**: Configurable allowed origins
- **SQL Injection**: Parameterized queries
- **XSS Protection**: Input sanitization
- **CSRF Protection**: Token-based validation

---

## 📊 Monitoring

### Metrics (Prometheus)
- Request rate, latency, errors
- Service health and availability
- Resource utilization
- Business metrics

### Logging (ELK Stack)
- Structured JSON logging
- Centralized log aggregation
- Log levels: DEBUG, INFO, WARN, ERROR
- Correlation IDs for tracing

### Dashboards (Grafana)
- System overview dashboard
- Voice service metrics
- Chat service metrics
- Business KPIs

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Architecture Inspiration**: Databricks, Snowflake, AWS
- **Voice AI**: Ultravox, Twilio
- **LLM**: OpenAI, Google Gemini
- **Vector Database**: Pinecone
- **Workflow Engine**: n8n
- **Framework**: FastAPI, Next.js

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **API Reference**: http://localhost:8000/docs
- **GitHub Issues**: [Create an issue](https://github.com/your-org/unified-agent/issues)
- **Email**: support@unified-agent.com

---

**Built with ❤️ by the Unified Agent Team**

**Version**: 1.0.0
**Last Updated**: February 7, 2026
