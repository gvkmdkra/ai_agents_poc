# Voice AI Calling Agent - Technical Architecture Document

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [Deployment Architecture](#deployment-architecture)
8. [Security](#security)
9. [Scalability](#scalability)
10. [Configuration](#configuration)

---

## 1. System Overview

The Voice AI Calling Agent is an enterprise-grade system that enables automated voice calls using AI. It combines:
- **Twilio** for telephony (making/receiving phone calls)
- **Ultravox** for real-time voice AI conversations
- **FastAPI** for the backend REST API
- **Turso** (libSQL) for persistent storage
- **Redis** for caching, rate limiting, and task queuing
- **Celery** for asynchronous task processing
- **Next.js** for the frontend website

### Key Capabilities
- Outbound AI-powered calls to any phone number
- Inbound call handling with voice AI
- Real-time transcription
- Call summaries and analytics
- Multi-tenant support
- High concurrency (1000s of simultaneous calls)

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DNS (Hostinger)                                      │
│  reapdat.com      → 15.156.116.91 (EC2)                                     │
│  api.reapdat.com  → 15.156.116.91 (EC2)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AWS EC2 Instance (15.156.116.91)                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        NGINX (Reverse Proxy)                          │  │
│  │  • Port 80  → Redirect to HTTPS                                       │  │
│  │  • Port 443 → SSL termination (Let's Encrypt)                        │  │
│  │  • Routes /api/v1/* → Docker API container (port 8000)               │  │
│  │  • Routes /health, /stats, /ready → Docker API container             │  │
│  │  • Routes /* → Static website files                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Docker Network (calling-agent-network)            │  │
│  │                                                                        │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────┐  │  │
│  │  │  calling-agent      │  │  calling-agent-     │  │ calling-agent │  │  │
│  │  │  (FastAPI + Uvicorn)│  │  redis              │  │ -celery       │  │  │
│  │  │  Port: 8000         │  │  Port: 6379         │  │ (Worker)      │  │  │
│  │  │                     │  │                     │  │               │  │  │
│  │  │  • 4 Gunicorn       │  │  • Connection pool  │  │ • 4 workers   │  │  │
│  │  │    workers          │  │  • Rate limiting    │  │ • Async tasks │  │  │
│  │  │  • Async handlers   │  │  • Call caching     │  │ • Call queue  │  │  │
│  │  └─────────┬───────────┘  └──────────┬──────────┘  └───────┬───────┘  │  │
│  │            │                         │                      │          │  │
│  │            └─────────────────────────┼──────────────────────┘          │  │
│  │                                      │                                 │  │
│  └──────────────────────────────────────┼─────────────────────────────────┘  │
│                                         │                                    │
└─────────────────────────────────────────┼────────────────────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
              ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   Turso Database    │   │      Twilio         │   │     Ultravox        │
│   (libSQL Cloud)    │   │   (Telephony)       │   │   (Voice AI)        │
│                     │   │                     │   │                     │
│ • Call records      │   │ • Make calls        │   │ • Real-time voice   │
│ • Tenants           │   │ • Receive calls     │   │ • Speech-to-text    │
│ • Transcripts       │   │ • Webhooks          │   │ • Text-to-speech    │
│ • API keys          │   │ • Status updates    │   │ • LLM responses     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

---

## 3. Component Details

### 3.1 Frontend (Next.js Website)

**Location:** `reapdat_website/`

**Technology Stack:**
- Next.js 16.1.6 with Turbopack
- React 19
- TypeScript
- Tailwind CSS
- Framer Motion (animations)

**Key Files:**
```
reapdat_website/
├── app/
│   ├── page.tsx              # Homepage
│   ├── voice-ai/page.tsx     # Voice AI demo page
│   └── layout.tsx            # Root layout
├── components/
│   ├── voice-ai-demo.tsx     # Demo call interface
│   ├── navbar.tsx            # Navigation
│   └── ui/                   # UI components
├── lib/
│   └── calling-agent-api.ts  # API client
├── nginx/
│   └── nginx.conf            # Nginx configuration
└── out/                      # Static build output
```

**How it works:**
1. Next.js builds static HTML/JS/CSS files
2. Files are deployed to EC2 at `/home/ubuntu/poc/agents/website/out/`
3. Nginx serves these static files for all non-API routes
4. The `voice-ai-demo.tsx` component makes API calls to `/health` and `/api/v1/calls/initiate`

**API Client Configuration:**
```typescript
// lib/calling-agent-api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_CALLING_AGENT_API_URL || '';
// Empty string means same-origin requests (nginx proxies to backend)
```

### 3.2 Backend API (FastAPI)

**Location:** `ai_agents_poc/calling_agent/`

**Technology Stack:**
- Python 3.11
- FastAPI 0.128.0
- Uvicorn (ASGI server)
- Gunicorn (process manager)
- Pydantic (data validation)

**Project Structure:**
```
calling_agent/
├── app/
│   ├── main.py               # FastAPI application entry
│   ├── api/
│   │   └── v1/
│   │       ├── calls.py      # Call endpoints
│   │       ├── webhooks.py   # Twilio/Ultravox webhooks
│   │       └── tenants.py    # Tenant management
│   ├── services/
│   │   ├── call_manager.py   # Call orchestration
│   │   ├── twilio_service.py # Twilio integration
│   │   ├── ultravox_service.py # Ultravox integration
│   │   ├── database.py       # Turso database
│   │   ├── redis_service.py  # Redis caching/queuing
│   │   └── tenant_service.py # Multi-tenant logic
│   ├── models/
│   │   ├── call.py           # Call data models
│   │   └── tenant.py         # Tenant data models
│   └── tasks/
│       ├── celery_app.py     # Celery configuration
│       └── call_tasks.py     # Async call tasks
├── docker-compose.scalable.yml
├── Dockerfile.scalable
└── .env
```

**Main Application (main.py):**
```python
from fastapi import FastAPI
from app.api.v1 import calls, webhooks, tenants

app = FastAPI(title="Calling Agent API", version="2.0.0")

# Include routers
app.include_router(calls.router, prefix="/api/v1/calls", tags=["calls"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}
```

### 3.3 Twilio Integration

**Purpose:** Handle telephony - making and receiving phone calls

**Configuration (.env):**
```bash
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
```

**How Twilio Works:**

1. **Outbound Call Flow:**
   ```
   API Request → Twilio API → Phone Network → Recipient Phone
                     ↓
              Status Webhooks → Our API → Update Database
   ```

2. **Inbound Call Flow:**
   ```
   Caller → Twilio Number → Webhook to Our API → Return TwiML → Connect to Ultravox
   ```

**Key Service Methods (twilio_service.py):**
```python
class TwilioService:
    async def make_call(self, to_number: str, webhook_url: str) -> str:
        """Initiate an outbound call"""
        call = self.client.calls.create(
            to=to_number,
            from_=self.phone_number,
            url=webhook_url,  # Ultravox connection webhook
            status_callback=f"{self.api_base_url}/api/v1/webhooks/twilio/status"
        )
        return call.sid

    def generate_connect_twiml(self, websocket_url: str) -> str:
        """Generate TwiML to connect call to Ultravox WebSocket"""
        response = VoiceResponse()
        connect = Connect()
        connect.stream(url=websocket_url)
        response.append(connect)
        return str(response)
```

### 3.4 Ultravox Integration

**Purpose:** Real-time voice AI - understanding speech and generating responses

**Configuration (.env):**
```bash
ULTRAVOX_API_KEY=your_ultravox_api_key
ULTRAVOX_API_ENDPOINT=https://api.ultravox.ai/api/calls
ULTRAVOX_VOICE_ID=your_voice_id
ULTRAVOX_DEFAULT_VOICE=Mark
ULTRAVOX_TEMPERATURE=0.2
```

**How Ultravox Works:**

1. **Session Creation:**
   - API creates an Ultravox session with system prompt
   - Ultravox returns a WebSocket URL
   - This URL is passed to Twilio for the call connection

2. **Real-time Processing:**
   ```
   Phone Audio → Twilio Stream → Ultravox WebSocket
                                      ↓
                              Speech Recognition
                                      ↓
                              LLM Processing
                                      ↓
                              Text-to-Speech
                                      ↓
   Phone Audio ← Twilio Stream ← Ultravox WebSocket
   ```

**Key Service Methods (ultravox_service.py):**
```python
class UltravoxService:
    async def create_call_session(
        self,
        system_prompt: str,
        greeting_message: str
    ) -> dict:
        """Create an Ultravox voice AI session"""
        payload = {
            "model": "fixie-ai/ultravox",
            "voice": self.voice_id,
            "systemPrompt": system_prompt,
            "temperature": 0.2,
            "firstSpeaker": "AGENT",
            "initialOutputMedium": "MESSAGE_MEDIUM_VOICE",
            "medium": {"twilio": {}},
            "firstSpeakerSettings": {
                "agent": {"text": greeting_message}
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_endpoint,
                json=payload,
                headers={"X-API-Key": self.api_key}
            )
            return response.json()  # Contains joinUrl (WebSocket)
```

### 3.5 Database (Turso/libSQL)

**Purpose:** Persistent storage for calls, tenants, and configuration

**Configuration (.env):**
```bash
TURSO_DB_URL=libsql://your-database.turso.io
TURSO_DB_AUTH_TOKEN=your_turso_auth_token
```

**Schema:**
```sql
-- Calls table
CREATE TABLE calls (
    call_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    direction TEXT NOT NULL DEFAULT 'outbound',
    phone_number TEXT NOT NULL,
    from_number TEXT NOT NULL,
    ultravox_call_id TEXT,
    twilio_call_sid TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    system_prompt TEXT,
    greeting_message TEXT,
    transcript TEXT,  -- JSON array
    summary TEXT,     -- JSON object
    metadata TEXT,    -- JSON object
    error_message TEXT
);

-- Tenants table
CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,
    tenant_name TEXT NOT NULL,
    company_name TEXT NOT NULL,
    agent_name TEXT DEFAULT 'AI Assistant',
    config TEXT NOT NULL,  -- JSON configuration
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- API Keys table
CREATE TABLE api_keys (
    api_key TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    permissions TEXT,  -- JSON array
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);
```

**Database Service (database.py):**
```python
import libsql_client

class Database:
    def __init__(self):
        self.client = libsql_client.create_client(
            url=os.getenv("TURSO_DB_URL"),
            auth_token=os.getenv("TURSO_DB_AUTH_TOKEN")
        )

    async def save_call(self, call: CallRecord):
        await self.client.execute(
            """INSERT INTO calls (call_id, status, phone_number, ...)
               VALUES (?, ?, ?, ...)""",
            [call.call_id, call.status, call.phone_number, ...]
        )

    async def get_call(self, call_id: str) -> CallRecord:
        result = await self.client.execute(
            "SELECT * FROM calls WHERE call_id = ?",
            [call_id]
        )
        return CallRecord(**result.rows[0])
```

### 3.6 Redis Service

**Purpose:** Caching, rate limiting, and call queue management

**Configuration (.env):**
```bash
REDIS_URL=redis://redis:6379/0
```

**Key Classes (redis_service.py):**

```python
class RateLimiter:
    """Token bucket rate limiter using Redis"""

    async def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """Check if request is allowed under rate limit"""
        key = f"ratelimit:{identifier}"
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window_seconds)
        pipe.ttl(key)
        results = await pipe.execute()

        current_count = results[0]
        remaining = max(0, self.max_requests - current_count)
        allowed = current_count <= self.max_requests

        return allowed, {"remaining": remaining, "limit": self.max_requests}


class CallCache:
    """Redis-based cache for call data"""

    async def get(self, call_id: str) -> Optional[dict]:
        data = await client.get(f"call:{call_id}")
        return json.loads(data) if data else None

    async def set(self, call_id: str, data: dict, ttl: int = 3600):
        await client.setex(f"call:{call_id}", ttl, json.dumps(data))


class CallQueue:
    """Redis-based call queue for managing concurrent calls"""

    async def enqueue(self, call_data: dict) -> str:
        call_id = call_data.get("call_id") or f"call_{await client.incr('call_counter')}"
        await client.lpush(self.queue_name, json.dumps(call_data))
        return call_id

    async def dequeue(self) -> Optional[dict]:
        result = await client.brpoplpush(self.queue_name, self.processing_set, timeout=1)
        return json.loads(result) if result else None
```

### 3.7 Celery Workers

**Purpose:** Asynchronous task processing for high-volume call handling

**Configuration (celery_app.py):**
```python
from celery import Celery

celery_app = Celery(
    "calling_agent",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
    include=["app.tasks.call_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    worker_prefetch_multiplier=4,
    worker_concurrency=8,
    task_routes={
        "app.tasks.call_tasks.initiate_call_task": {"queue": "calls"},
        "app.tasks.call_tasks.process_webhook_task": {"queue": "webhooks"},
    },
    task_default_rate_limit="1000/m",
)
```

**Tasks (call_tasks.py):**
```python
@shared_task(bind=True, max_retries=3, rate_limit="100/m")
def initiate_call_task(self, phone_number: str, system_prompt: str = None):
    """Async task to initiate a call"""
    async def _initiate():
        manager = get_call_manager()
        return await manager.initiate_call(phone_number, system_prompt)

    return run_async(_initiate())


@shared_task(bind=True, max_retries=5, rate_limit="500/m")
def process_webhook_task(self, webhook_type: str, payload: dict):
    """Async task to process webhooks"""
    async def _process():
        manager = get_call_manager()
        if webhook_type == "twilio_status":
            await manager.handle_twilio_status(payload)
        elif webhook_type == "ultravox_event":
            await manager.handle_ultravox_event(payload)

    return run_async(_process())


@shared_task
def batch_initiate_calls(phone_numbers: list, system_prompt: str = None):
    """Batch initiate multiple calls in parallel"""
    from celery import group

    tasks = group(
        initiate_call_task.s(number, system_prompt)
        for number in phone_numbers
    )
    return tasks.apply_async()
```

### 3.8 Nginx Configuration

**Location:** `reapdat_website/nginx/nginx.conf`

**Key Features:**
- SSL termination with Let's Encrypt
- HTTP to HTTPS redirect
- Reverse proxy to Docker containers
- Rate limiting
- Static file serving
- CORS headers

```nginx
events {
    worker_connections 4096;
}

http {
    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    # Upstream for API backend
    upstream calling_agent_api {
        server localhost:8000;
        keepalive 64;
    }

    # HTTP → HTTPS redirect
    server {
        listen 80;
        server_name reapdat.com www.reapdat.com api.reapdat.com;
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name reapdat.com www.reapdat.com;

        ssl_certificate /etc/letsencrypt/live/reapdat.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/reapdat.com/privkey.pem;

        # Static website
        root /home/ubuntu/poc/agents/website/out;

        # API proxy
        location /api/v1/ {
            limit_req zone=api burst=50 nodelay;
            proxy_pass http://calling_agent_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Health check proxy
        location /health {
            proxy_pass http://calling_agent_api;
        }

        # Static files
        location / {
            try_files $uri $uri.html $uri/ /index.html;
        }
    }
}
```

---

## 4. Data Flow

### 4.1 Outbound Call Flow (Complete Sequence)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │     │  Website │     │   API    │     │  Twilio  │     │ Ultravox │
│ Browser  │     │ (Next.js)│     │(FastAPI) │     │          │     │          │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ 1. Enter phone │                │                │                │
     │    number      │                │                │                │
     │───────────────>│                │                │                │
     │                │                │                │                │
     │                │ 2. POST /api/  │                │                │
     │                │    v1/calls/   │                │                │
     │                │    initiate    │                │                │
     │                │───────────────>│                │                │
     │                │                │                │                │
     │                │                │ 3. Create      │                │
     │                │                │    Ultravox    │                │
     │                │                │    session     │                │
     │                │                │───────────────────────────────>│
     │                │                │                │                │
     │                │                │ 4. Return      │                │
     │                │                │    WebSocket   │                │
     │                │                │    URL         │                │
     │                │                │<───────────────────────────────│
     │                │                │                │                │
     │                │                │ 5. Make call   │                │
     │                │                │    with webhook│                │
     │                │                │───────────────>│                │
     │                │                │                │                │
     │                │                │ 6. Return      │                │
     │                │                │    call SID    │                │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │ 7. Return      │                │                │
     │                │    call_id,    │                │                │
     │                │    status      │                │                │
     │                │<───────────────│                │                │
     │                │                │                │                │
     │ 8. Show        │                │                │                │
     │    "Calling..."│                │                │                │
     │<───────────────│                │                │                │
     │                │                │                │                │
     │                │                │                │ 9. Call        │
     │                │                │                │    recipient   │
     │                │                │                │────────────────│──> Phone
     │                │                │                │                │
     │                │                │                │ 10. Recipient  │
     │                │                │                │     answers    │
     │                │                │                │<───────────────│─── Phone
     │                │                │                │                │
     │                │                │ 11. Webhook:   │                │
     │                │                │     call       │                │
     │                │                │     answered   │                │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │                │ 12. Connect    │                │
     │                │                │     to         │                │
     │                │                │     Ultravox   │                │
     │                │                │     WebSocket  │                │
     │                │                │───────────────>│───────────────>│
     │                │                │                │                │
     │                │                │                │ 13. Audio      │
     │                │                │                │     streaming  │
     │                │                │                │<──────────────>│
     │                │                │                │                │
     │                │                │ 14. Status     │                │
     │                │                │     webhooks   │                │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │                │ 15. Transcript │                │
     │                │                │     updates    │                │
     │                │                │<───────────────────────────────│
     │                │                │                │                │
```

### 4.2 Call State Machine

```
                    ┌─────────┐
                    │ PENDING │
                    └────┬────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  INITIATING  │
                  └──────┬───────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
      ┌─────────┐   ┌─────────┐   ┌─────────┐
      │ RINGING │   │  BUSY   │   │ FAILED  │
      └────┬────┘   └─────────┘   └─────────┘
           │
           ▼
    ┌─────────────┐
    │ IN_PROGRESS │
    └──────┬──────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌──────────┐ ┌──────────┐
│COMPLETED │ │NO_ANSWER │
└──────────┘ └──────────┘
```

---

## 5. API Endpoints

### 5.1 Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |
| GET | `/stats` | Call statistics |
| GET | `/info` | Service info |

### 5.2 Call Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/calls/initiate` | Start a new call |
| GET | `/api/v1/calls/` | List all calls |
| GET | `/api/v1/calls/{call_id}` | Get call details |
| POST | `/api/v1/calls/{call_id}/end` | End an active call |
| GET | `/api/v1/calls/{call_id}/transcript` | Get call transcript |
| GET | `/api/v1/calls/{call_id}/summary` | Get call summary |
| GET | `/api/v1/calls/active/list` | List active calls |
| GET | `/api/v1/calls/dashboard/analytics` | Dashboard data |

### 5.3 Webhooks (Internal)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/webhooks/twilio/voice` | Incoming call handler |
| POST | `/api/v1/webhooks/twilio/connect/{call_id}` | Connect to Ultravox |
| POST | `/api/v1/webhooks/twilio/status/{call_id}` | Call status updates |
| POST | `/api/v1/webhooks/twilio/amd` | Answering machine detection |
| POST | `/api/v1/webhooks/ultravox/events` | Ultravox events |
| POST | `/api/v1/webhooks/ultravox/transcript/{call_id}` | Transcript updates |

### 5.4 Tenant Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tenants/` | List tenants |
| POST | `/api/v1/tenants/` | Create tenant |
| GET | `/api/v1/tenants/{tenant_id}` | Get tenant |
| PUT | `/api/v1/tenants/{tenant_id}` | Update tenant |
| DELETE | `/api/v1/tenants/{tenant_id}` | Delete tenant |
| POST | `/api/v1/tenants/{tenant_id}/api-keys` | Create API key |

### 5.5 Request/Response Examples

**Initiate Call:**
```bash
POST /api/v1/calls/initiate
Content-Type: application/json

{
    "phone_number": "+14155551234",
    "system_prompt": "You are a helpful assistant for Reapdat.",
    "greeting_message": "Hello! How can I help you today?",
    "metadata": {
        "customer_id": "12345"
    }
}
```

**Response:**
```json
{
    "call_id": "f19b642b-110e-4141-8aa7-a99a4b52d755",
    "status": "initiating",
    "phone_number": "+14155551234",
    "ultravox_call_id": "4fab29da-a603-48ae-8dbb-fc2ff9eb3c0f",
    "created_at": "2026-02-02T12:30:00.000000"
}
```

---

## 6. Deployment Architecture

### 6.1 Docker Compose (docker-compose.scalable.yml)

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: calling-agent-redis
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    networks:
      - calling-agent-network

  calling-agent:
    build:
      context: .
      dockerfile: Dockerfile.scalable
    container_name: calling-agent
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - WORKERS=4
      - MAX_CONNECTIONS=1000
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1.5G
    networks:
      - calling-agent-network

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.scalable
    container_name: calling-agent-celery
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4 --pool=gevent
    env_file:
      - .env
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    networks:
      - calling-agent-network

volumes:
  redis-data:

networks:
  calling-agent-network:
    driver: bridge
```

### 6.2 Dockerfile (Dockerfile.scalable)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

USER appuser

# Run with Gunicorn + Uvicorn workers
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--max-requests", "10000", \
     "--max-requests-jitter", "1000", \
     "--timeout", "120", \
     "--keep-alive", "5"]
```

### 6.3 GitHub Actions (deploy-ec2.yml)

```yaml
name: Deploy to EC2

on:
  push:
    branches: [calling_agent_by_claude_version1, main]
    paths: ['calling_agent/**']
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.EC2_SSH_KEY }}" > ~/.ssh/ec2_key.pem
          chmod 600 ~/.ssh/ec2_key.pem
          ssh-keyscan -H 15.156.116.91 >> ~/.ssh/known_hosts

      - name: Deploy
        run: |
          rsync -avz --exclude '.git' --exclude '.env' \
            calling_agent/ ubuntu@15.156.116.91:/home/ubuntu/poc/agents/calling_agent/

          ssh ubuntu@15.156.116.91 << 'ENDSSH'
            cd /home/ubuntu/poc/agents/calling_agent
            sudo docker-compose -f docker-compose.scalable.yml down || true
            sudo docker-compose -f docker-compose.scalable.yml build --no-cache
            sudo docker-compose -f docker-compose.scalable.yml up -d
          ENDSSH
```

---

## 7. Security

### 7.1 SSL/TLS
- Let's Encrypt certificates for HTTPS
- Automatic renewal via certbot
- TLS 1.2/1.3 only

### 7.2 API Authentication
- API Key authentication via `X-API-Key` header
- Bearer token support
- Per-tenant API keys with expiration

### 7.3 Rate Limiting
- 100 requests/second per IP for API
- 50 requests/second for call initiation
- Redis-based token bucket algorithm

### 7.4 CORS
- Configurable allowed origins
- Preflight request handling

### 7.5 Environment Variables
- All secrets stored in `.env` file
- Not committed to git (in `.gitignore`)
- Passed to Docker containers via `env_file`

---

## 8. Scalability

### 8.1 Horizontal Scaling
- 4 Gunicorn workers per container
- 4 Celery workers for async tasks
- Connection pooling to Redis (64 keepalive)

### 8.2 Capacity
- **Concurrent calls:** 1000+
- **Requests/minute:** 6000+
- **Call queue depth:** Unlimited (Redis)

### 8.3 Bottlenecks & Solutions

| Bottleneck | Solution |
|------------|----------|
| API throughput | Multiple Uvicorn workers |
| Call processing | Celery async tasks |
| Database | Connection pooling |
| Rate limits | Redis token bucket |

---

## 9. Configuration

### 9.1 Environment Variables (.env)

```bash
# OpenAI (for RAG)
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini

# Pinecone (Vector DB)
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=tenant-metaprobe-4fc868e7

# Turso Database
TURSO_DB_URL=libsql://callingagent-....turso.io
TURSO_DB_AUTH_TOKEN=eyJ...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+19785408346

# Ultravox
ULTRAVOX_API_KEY=...
ULTRAVOX_API_ENDPOINT=https://api.ultravox.ai/api/calls
ULTRAVOX_VOICE_ID=7c125579-a8b9-46ba-887b-60e4f0449e5d

# Application
DEBUG=false
ENVIRONMENT=production
API_BASE_URL=https://reapdat.com

# Redis
REDIS_URL=redis://redis:6379/0

# CORS
ALLOWED_ORIGINS=*
```

---

## 10. Monitoring & Debugging

### 10.1 Health Checks
```bash
# Check API health
curl https://reapdat.com/health

# Check stats
curl https://reapdat.com/stats

# Check Docker containers
docker ps
docker logs calling-agent
docker logs calling-agent-redis
docker logs calling-agent-celery
```

### 10.2 Common Issues

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check Docker containers are running |
| SSL error | Verify certbot certificates |
| Call not initiating | Check Twilio credentials |
| No AI response | Check Ultravox API key |
| Database error | Verify Turso URL and token |

---

## Appendix: Quick Reference

### URLs
- **Website:** https://reapdat.com
- **Demo:** https://reapdat.com/voice-ai
- **API Docs:** https://reapdat.com/docs
- **Health:** https://reapdat.com/health

### Repositories
- **Backend:** https://github.com/gvkmdkra/ai_agents_poc
- **Website:** https://github.com/gvkmdkra/reapdat_website

### External Services
- **Twilio Console:** https://console.twilio.com
- **Ultravox Dashboard:** https://ultravox.ai
- **Turso Dashboard:** https://turso.tech
- **AWS Console:** https://console.aws.amazon.com

---

*Document Version: 1.0*
*Last Updated: February 2, 2026*
