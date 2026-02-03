# Unified AI Agent

A comprehensive AI agent platform that combines voice calling, RAG-powered chat, and Text-to-SQL capabilities in a single, unified solution.

## Features

- **Voice Calling**: Browser-based WebRTC calls and outbound phone calls via Twilio + Ultravox AI
- **RAG Chat**: Document search and retrieval using Pinecone vector database
- **Text-to-SQL**: Natural language database queries with user data isolation
- **Multi-Tenant**: Full multi-tenant support with API key authentication
- **Lead Capture**: Automatic lead extraction from conversations
- **Analytics**: Call and chat analytics dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED AI AGENT                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Voice API  │  │   Chat API   │  │  Tenant API  │  │ Webhook API  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │                  │        │
│  ┌──────┴──────────────────┴──────────────────┴──────────────────┴─────┐ │
│  │                        Service Layer                                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │ │
│  │  │   Voice     │  │    Chat     │  │  Text-to-   │  │   Tenant    │ │ │
│  │  │  Calling    │  │   Service   │  │    SQL      │  │   Service   │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                     External Integrations                            │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │ │
│  │  │Ultravox │  │ Twilio  │  │ OpenAI  │  │Pinecone │  │  MySQL  │  │ │
│  │  │(Voice AI)│  │(Phone)  │  │ (LLM)   │  │(Vectors)│  │ (Data)  │  │ │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                       Data Layer                                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │ │
│  │  │    Turso    │  │   Redis     │  │   SQLite    │                 │ │
│  │  │  (Primary)  │  │  (Cache)    │  │ (Fallback)  │                 │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- API keys for: OpenAI, Ultravox, Twilio, Pinecone

### Local Development

1. Clone and setup:
```bash
cd unified_agent
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Run the application:
```bash
uvicorn app.main:app --reload
```

4. Visit http://localhost:8000/docs for API documentation

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f unified-agent

# Stop services
docker-compose down
```

## API Endpoints

### Voice Calling

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/calls/initiate` | POST | Start a voice call |
| `/api/v1/calls/{call_id}` | GET | Get call status |
| `/api/v1/calls/` | GET | List calls |
| `/api/v1/calls/{call_id}/end` | POST | End a call |
| `/api/v1/calls/dashboard/analytics` | GET | Get call analytics |

### Chat

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/message` | POST | Send chat message |
| `/api/v1/chat/history/{session_id}` | GET | Get chat history |
| `/api/v1/chat/widget/config/{tenant_id}` | GET | Get widget config |
| `/api/v1/chat/widget/voice-call` | POST | Start browser voice call |

### Tenant Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tenants/` | GET | List tenants |
| `/api/v1/tenants/` | POST | Create tenant |
| `/api/v1/tenants/{tenant_id}` | GET | Get tenant |
| `/api/v1/tenants/{tenant_id}` | PATCH | Update tenant |
| `/api/v1/tenants/{tenant_id}/api-keys` | POST | Create API key |

### Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/ready` | GET | Readiness check |
| `/health/live` | GET | Liveness check |
| `/health/detailed` | GET | Detailed health info |

## Authentication

### API Key Authentication

Include your API key in requests:

```bash
# Header method (recommended)
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/calls/

# Bearer token method
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/api/v1/calls/
```

### JWT Authentication (for database access)

For Text-to-SQL queries with user data isolation, include a JWT token:

```bash
curl -H "X-API-Key: your-api-key" \
     -H "Authorization: Bearer your-jwt-token" \
     http://localhost:8000/api/v1/chat/message
```

## Configuration

See `.env.example` for all configuration options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_TYPE` | Database type (turso, sqlite, postgres) | turso |
| `ENABLE_VOICE_CALLING` | Enable voice features | true |
| `ENABLE_TEXT_TO_SQL` | Enable database queries | true |
| `ENABLE_RAG` | Enable document search | true |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Request rate limit | 60 |

## Multi-Tenant Setup

1. Create a tenant:
```bash
curl -X POST http://localhost:8000/api/v1/tenants/ \
  -H "X-API-Key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme"}'
```

2. Create an API key:
```bash
curl -X POST http://localhost:8000/api/v1/tenants/{tenant_id}/api-keys \
  -H "X-API-Key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Key", "can_call": true, "can_chat": true}'
```

## Development

### Project Structure

```
unified_agent/
├── app/
│   ├── api/
│   │   ├── middleware/     # Auth, rate limiting
│   │   └── routes/         # API endpoints
│   ├── core/               # Config, logging, exceptions
│   ├── db/                 # Database models and management
│   ├── services/           # Business logic
│   └── main.py             # FastAPI application
├── static/                 # Static files
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black app/
isort app/
mypy app/
```

## License

Proprietary - All rights reserved
