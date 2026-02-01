# VoiceAI Calling Agent - Technical Architecture

## Executive Summary

The VoiceAI Calling Agent is an enterprise-grade AI-powered telephony solution that enables businesses to automate inbound and outbound phone calls using natural language processing and real-time voice AI. The system integrates multiple cloud services to deliver human-like conversations, real-time transcription, sentiment analysis, and actionable insights.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          VOICEAI CALLING AGENT PLATFORM                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Website   │    │  Dashboard  │    │   Mobile    │    │    API      │      │
│  │  (Next.js)  │    │  (Frontend) │    │    App      │    │  Clients    │      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘      │
│         │                  │                  │                  │              │
│         └──────────────────┴──────────────────┴──────────────────┘              │
│                                    │                                            │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         API GATEWAY / LOAD BALANCER                      │   │
│  │                    (nginx / AWS ALB / Cloudflare)                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         FASTAPI BACKEND SERVER                           │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │   │
│  │  │   Call    │  │  Webhook  │  │  Analytics│  │   Auth    │            │   │
│  │  │  Manager  │  │  Handler  │  │  Service  │  │  Service  │            │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│         ┌──────────────────────────┼──────────────────────────┐                │
│         ▼                          ▼                          ▼                │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐          │
│  │   TWILIO    │           │  ULTRAVOX   │           │   OPENAI    │          │
│  │ (Telephony) │◄─────────►│ (Voice AI)  │◄─────────►│   (LLM)     │          │
│  └─────────────┘           └─────────────┘           └─────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Components

### 2.1 Presentation Layer

#### Marketing Website (reapdat.com)
- **Technology**: Next.js 15, React 19, TailwindCSS
- **Hosting**: Hostinger (Static Export)
- **Deployment**: GitHub Actions → FTP Deploy
- **Purpose**: Product showcase, landing pages, lead generation

#### Dashboard Frontend
- **Technology**: HTML5, CSS3, Vanilla JavaScript
- **Features**: Real-time call monitoring, analytics, transcript viewer
- **Communication**: REST API + WebSocket for live updates

### 2.2 Application Layer

#### FastAPI Backend Server
```
app/
├── api/
│   └── routes/
│       ├── calls.py          # Call management endpoints
│       └── webhooks.py       # Twilio/Ultravox webhook handlers
├── core/
│   ├── config.py             # Configuration management
│   └── logging.py            # Structured logging
├── models/
│   └── call.py               # Pydantic data models
└── services/
    ├── call_manager.py       # Call orchestration logic
    ├── voice/
    │   └── ultravox_service.py   # Ultravox API integration
    ├── telephony/
    │   └── twilio_service.py     # Twilio API integration
    └── llm/
        └── openai_service.py     # OpenAI API integration
```

### 2.3 Integration Layer

#### Twilio (Telephony Provider)
- **Purpose**: PSTN connectivity, call routing
- **Features Used**:
  - Programmable Voice API
  - TwiML for call flow control
  - WebSocket Media Streams
  - Status Callbacks

#### Ultravox (Voice AI Engine)
- **Purpose**: Real-time voice conversations
- **Features Used**:
  - WebRTC/WebSocket voice streaming
  - Real-time speech-to-text
  - Natural language understanding
  - Text-to-speech synthesis

#### OpenAI (Language Model)
- **Purpose**: Call analysis and summarization
- **Models Used**: GPT-4o-mini
- **Features**:
  - Conversation summarization
  - Sentiment analysis
  - Key topic extraction
  - Action item identification

---

## 3. Data Flow Architecture

### 3.1 Outbound Call Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │  FastAPI │     │ Ultravox │     │  Twilio  │     │   PSTN   │
│Dashboard │     │  Server  │     │    AI    │     │  Cloud   │     │ Network  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ 1. POST /calls/initiate         │                │                │
     │────────────────>                │                │                │
     │                │                │                │                │
     │                │ 2. Create Voice Session         │                │
     │                │───────────────>│                │                │
     │                │                │                │                │
     │                │ 3. Return join_url              │                │
     │                │<───────────────│                │                │
     │                │                │                │                │
     │                │ 4. Initiate Call (TwiML URL)    │                │
     │                │────────────────────────────────>│                │
     │                │                │                │                │
     │                │                │                │ 5. Dial Phone  │
     │                │                │                │───────────────>│
     │                │                │                │                │
     │                │                │                │ 6. Call Answered
     │                │                │                │<───────────────│
     │                │                │                │                │
     │                │ 7. Webhook: /connect/{call_id}  │                │
     │                │<────────────────────────────────│                │
     │                │                │                │                │
     │                │ 8. Return TwiML with Stream URL │                │
     │                │────────────────────────────────>│                │
     │                │                │                │                │
     │                │                │ 9. WebSocket Audio Stream       │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │                │ 10. AI Conversation             │
     │                │                │<──────────────>│<──────────────>│
     │                │                │                │                │
     │ 11. Real-time Status Updates    │                │                │
     │<────────────────                │                │                │
     │                │                │                │                │
```

### 3.2 Inbound Call Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   PSTN   │     │  Twilio  │     │  FastAPI │     │ Ultravox │
│  Caller  │     │  Cloud   │     │  Server  │     │    AI    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Incoming Call               │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. POST /webhooks/twilio/voice  │
     │                │───────────────>│                │
     │                │                │                │
     │                │                │ 3. Create Session
     │                │                │───────────────>│
     │                │                │                │
     │                │                │ 4. Return join_url
     │                │                │<───────────────│
     │                │                │                │
     │                │ 5. TwiML: <Stream> to Ultravox  │
     │                │<───────────────│                │
     │                │                │                │
     │ 6. Audio Stream via WebSocket  │                │
     │<──────────────>│<──────────────────────────────>│
     │                │                │                │
     │ 7. AI Handles Conversation     │                │
     │<──────────────────────────────────────────────>│
     │                │                │                │
```

### 3.3 Post-Call Analysis Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Twilio  │     │  FastAPI │     │  OpenAI  │     │ Storage  │
│ Callback │     │  Server  │     │   API    │     │  (JSON)  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Call Completed Webhook      │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. Retrieve Transcript          │
     │                │──────────────────────────────────────────────>│
     │                │                │                │              │
     │                │ 3. Send for Analysis            │              │
     │                │───────────────>│                │              │
     │                │                │                │              │
     │                │ 4. Return Summary + Sentiment   │              │
     │                │<───────────────│                │              │
     │                │                │                │              │
     │                │ 5. Store Analysis Results       │              │
     │                │──────────────────────────────────────────────>│
     │                │                │                │              │
```

---

## 4. Component Details

### 4.1 Call Manager Service

The central orchestrator managing call lifecycle:

```python
class CallManager:
    """
    Responsibilities:
    - Call initiation and termination
    - State management (PENDING → RINGING → IN_PROGRESS → COMPLETED)
    - Transcript aggregation
    - Summary generation triggering
    - Call history persistence
    """

    # State Management
    active_calls: Dict[str, CallRecord]      # Currently active calls
    call_history: List[CallRecord]           # Completed call records

    # Service Dependencies
    ultravox: UltravoxService                # Voice AI service
    twilio: TwilioService                    # Telephony service
    openai: OpenAIService                    # LLM service
```

### 4.2 Data Models

```python
class CallRecord:
    call_id: str                    # Unique identifier (UUID)
    status: CallStatus              # PENDING|RINGING|IN_PROGRESS|COMPLETED|FAILED
    direction: CallDirection        # INBOUND|OUTBOUND
    phone_number: str               # Target/source phone (E.164)
    from_number: str                # Twilio number used
    ultravox_call_id: str          # Ultravox session ID
    twilio_call_sid: str           # Twilio call SID
    system_prompt: str             # AI agent instructions
    transcript: List[CallTranscript]  # Conversation log
    summary: CallSummary           # AI-generated analysis
    created_at: datetime
    started_at: datetime
    ended_at: datetime
    duration_seconds: int

class CallTranscript:
    timestamp: datetime
    speaker: str                   # "agent" | "user"
    text: str                      # Transcribed text
    confidence: float              # STT confidence score

class CallSummary:
    summary: str                   # Brief conversation summary
    key_points: List[str]          # Main discussion points
    sentiment: str                 # "positive"|"neutral"|"negative"
    action_items: List[str]        # Follow-up tasks identified
```

### 4.3 API Endpoints

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            REST API ENDPOINTS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CALL MANAGEMENT                                                        │
│  ───────────────                                                        │
│  POST   /api/v1/calls/initiate        Initiate outbound call           │
│  GET    /api/v1/calls/                List call history                 │
│  GET    /api/v1/calls/{call_id}       Get call details                  │
│  POST   /api/v1/calls/{call_id}/end   End active call                   │
│  GET    /api/v1/calls/{call_id}/transcript   Get call transcript        │
│  GET    /api/v1/calls/{call_id}/summary      Get call summary           │
│  POST   /api/v1/calls/{call_id}/analyze      Trigger AI analysis        │
│  GET    /api/v1/calls/active/list     List active calls                 │
│  GET    /api/v1/calls/dashboard/analytics    Dashboard metrics          │
│                                                                         │
│  WEBHOOKS (Internal - Twilio/Ultravox)                                  │
│  ─────────────────────────────────────                                  │
│  POST   /api/v1/webhooks/twilio/voice         Inbound call handler     │
│  POST   /api/v1/webhooks/twilio/connect/{id}  Media stream connection  │
│  POST   /api/v1/webhooks/twilio/status/{id}   Call status updates      │
│  POST   /api/v1/webhooks/ultravox/events      Ultravox event handler   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. External Service Integration

### 5.1 Twilio Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TWILIO CONFIGURATION                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Account Credentials                                                │
│  ───────────────────                                                │
│  TWILIO_ACCOUNT_SID     = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"     │
│  TWILIO_AUTH_TOKEN      = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"       │
│  TWILIO_PHONE_NUMBER    = "+1XXXXXXXXXX"                           │
│                                                                     │
│  Webhook Configuration                                              │
│  ─────────────────────                                              │
│  Voice URL:    https://{domain}/api/v1/webhooks/twilio/voice       │
│  Status URL:   https://{domain}/api/v1/webhooks/twilio/status/{id} │
│  Method:       POST                                                 │
│                                                                     │
│  TwiML Commands Used                                                │
│  ──────────────────                                                 │
│  <Response>                                                         │
│    <Connect>                                                        │
│      <Stream url="wss://ultravox.api/stream/{session}"/>           │
│    </Connect>                                                       │
│  </Response>                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Ultravox Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                       ULTRAVOX CONFIGURATION                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  API Configuration                                                  │
│  ─────────────────                                                  │
│  ULTRAVOX_API_KEY       = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"       │
│  ULTRAVOX_API_URL       = "https://api.ultravox.ai/api"            │
│                                                                     │
│  Session Parameters                                                 │
│  ──────────────────                                                 │
│  {                                                                  │
│    "systemPrompt": "You are a helpful AI assistant...",            │
│    "model": "fixie-ai/ultravox-70B",                               │
│    "voice": "Mark",                                                 │
│    "temperature": 0.7,                                              │
│    "medium": {                                                      │
│      "twilio": {}    // Twilio WebSocket integration               │
│    },                                                               │
│    "firstSpeakerSettings": {                                        │
│      "agent": {                                                     │
│        "uninterruptible": true,                                     │
│        "text": "Hello! How can I help you today?"                  │
│      }                                                              │
│    }                                                                │
│  }                                                                  │
│                                                                     │
│  Available Voices                                                   │
│  ────────────────                                                   │
│  Mark, Emily, Josh, Sarah, David, Jessica                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 OpenAI Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OPENAI CONFIGURATION                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  API Configuration                                                  │
│  ─────────────────                                                  │
│  OPENAI_API_KEY         = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"    │
│  OPENAI_MODEL           = "gpt-4o-mini"                            │
│                                                                     │
│  Analysis Prompt Template                                           │
│  ────────────────────────                                           │
│  """                                                                │
│  Analyze the following call transcript and provide:                 │
│  1. A brief summary (2-3 sentences)                                │
│  2. Key discussion points (bullet list)                            │
│  3. Overall sentiment (positive/neutral/negative)                  │
│  4. Action items identified                                        │
│  5. Conversation highlights                                        │
│                                                                     │
│  Transcript:                                                        │
│  {transcript}                                                       │
│                                                                     │
│  Return as JSON with keys: summary, key_topics, sentiment,         │
│  action_items, conversation_highlights                             │
│  """                                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Infrastructure Architecture

### 6.1 Development Environment

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT ENVIRONMENT                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Local Machine                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                             │   │
│  │  ┌───────────────┐    ┌───────────────┐                    │   │
│  │  │   FastAPI     │    │   Frontend    │                    │   │
│  │  │   Server      │    │   Dashboard   │                    │   │
│  │  │   :8000       │    │   (Static)    │                    │   │
│  │  └───────┬───────┘    └───────────────┘                    │   │
│  │          │                                                  │   │
│  │          ▼                                                  │   │
│  │  ┌───────────────┐                                         │   │
│  │  │  Cloudflared  │  ◄── Secure Tunnel                      │   │
│  │  │  Tunnel       │      (for webhooks)                     │   │
│  │  └───────┬───────┘                                         │   │
│  │          │                                                  │   │
│  └──────────┼──────────────────────────────────────────────────┘   │
│             │                                                       │
│             ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              INTERNET (Cloudflare Edge)                      │   │
│  │         https://xxx.trycloudflare.com                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Production Environment (Recommended)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ┌─────────────┐                                │
│                              │   Users /   │                                │
│                              │   Clients   │                                │
│                              └──────┬──────┘                                │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CLOUDFLARE (CDN/WAF)                          │   │
│  │              DDoS Protection, SSL, Caching, Rate Limiting            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
│              ┌──────────────────────┼──────────────────────┐               │
│              │                      │                      │               │
│              ▼                      ▼                      ▼               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │    Hostinger    │    │   AWS/GCP/Azure │    │   AWS/GCP/Azure │        │
│  │   (Static Web)  │    │    (API Server) │    │    (Database)   │        │
│  │                 │    │                 │    │                 │        │
│  │  - Next.js SSG  │    │  - FastAPI      │    │  - PostgreSQL   │        │
│  │  - Marketing    │    │  - Docker       │    │  - Redis Cache  │        │
│  │  - reapdat.com  │    │  - Auto-scaling │    │  - TimescaleDB  │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    EXTERNAL SERVICES (SaaS)                          │   │
│  │                                                                       │   │
│  │   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐       │   │
│  │   │ Twilio  │     │Ultravox │     │ OpenAI  │     │  Sentry │       │   │
│  │   │         │     │         │     │         │     │(Logging)│       │   │
│  │   └─────────┘     └─────────┘     └─────────┘     └─────────┘       │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Container Architecture (Docker)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY frontend/ ./frontend/

# Environment
ENV PYTHONPATH=/app
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - TWILIO_PHONE_NUMBER=${TWILIO_PHONE_NUMBER}
      - ULTRAVOX_API_KEY=${ULTRAVOX_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - API_BASE_URL=${API_BASE_URL}
    volumes:
      - ./call_records.json:/app/call_records.json
    restart: unless-stopped

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=voiceai
      - POSTGRES_USER=voiceai
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  redis_data:
  postgres_data:
```

---

## 7. Security Architecture

### 7.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: Network Security                                          │
│  ─────────────────────────                                          │
│  • Cloudflare DDoS protection                                       │
│  • WAF (Web Application Firewall)                                   │
│  • Rate limiting (100 req/min per IP)                              │
│  • IP whitelisting for admin endpoints                             │
│                                                                     │
│  Layer 2: Transport Security                                        │
│  ───────────────────────────                                        │
│  • TLS 1.3 encryption (all traffic)                                │
│  • HSTS headers enabled                                             │
│  • Certificate pinning for mobile apps                             │
│                                                                     │
│  Layer 3: Application Security                                      │
│  ─────────────────────────────                                      │
│  • JWT authentication (future)                                      │
│  • API key validation                                               │
│  • Input validation (Pydantic models)                              │
│  • CORS configuration                                               │
│  • Webhook signature verification (Twilio)                         │
│                                                                     │
│  Layer 4: Data Security                                             │
│  ───────────────────────                                            │
│  • Encryption at rest (AES-256)                                    │
│  • PII masking in logs                                              │
│  • Secure credential storage (env vars / secrets manager)          │
│  • Regular security audits                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Webhook Security

```python
# Twilio Webhook Validation
from twilio.request_validator import RequestValidator

def validate_twilio_request(request):
    validator = RequestValidator(settings.twilio_auth_token)

    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    params = dict(request.form)

    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
```

---

## 8. Monitoring & Observability

### 8.1 Metrics & Logging

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Metrics (Prometheus/CloudWatch)                                    │
│  ───────────────────────────────                                    │
│  • call_total{status, direction}      - Total calls counter        │
│  • call_duration_seconds              - Call duration histogram     │
│  • call_active_count                  - Current active calls       │
│  • api_request_duration_seconds       - API latency                │
│  • api_error_total{endpoint}          - Error counter              │
│  • ultravox_session_duration          - AI session time            │
│  • transcription_confidence_avg       - STT quality                │
│                                                                     │
│  Logging (Structured JSON)                                          │
│  ─────────────────────────                                          │
│  {                                                                  │
│    "timestamp": "2026-02-01T10:30:00Z",                            │
│    "level": "INFO",                                                 │
│    "service": "call_manager",                                       │
│    "call_id": "abc-123",                                           │
│    "event": "call_initiated",                                       │
│    "phone_number": "+1***5678",  // PII masked                     │
│    "duration_ms": 150                                               │
│  }                                                                  │
│                                                                     │
│  Tracing (OpenTelemetry)                                           │
│  ───────────────────────                                            │
│  • Distributed tracing across services                             │
│  • Call flow visualization                                          │
│  • Latency breakdown by component                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Dashboard Metrics

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DASHBOARD ANALYTICS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Real-Time Metrics                                                  │
│  ─────────────────                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │
│  │  Total  │  │ Success │  │   Avg   │  │ Active  │              │
│  │  Calls  │  │  Rate   │  │Duration │  │  Calls  │              │
│  │   248   │  │   96%   │  │  3.2m   │  │    12   │              │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘              │
│                                                                     │
│  Sentiment Distribution                                             │
│  ──────────────────────                                             │
│  Positive  ████████████████████░░░░░░░░░░  60%                    │
│  Neutral   █████████░░░░░░░░░░░░░░░░░░░░░  30%                    │
│  Negative  ███░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%                    │
│                                                                     │
│  Call Volume (24h)                                                  │
│  ─────────────────                                                  │
│       ▄                                                             │
│      ▄█▄     ▄                                                      │
│     ▄███▄   ▄█▄    ▄                                               │
│    ▄█████▄ ▄███▄  ▄█▄                                              │
│   ▄███████▄█████▄▄███▄                                             │
│  ─────────────────────────                                          │
│   00  04  08  12  16  20  24                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Scalability Considerations

### 9.1 Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SCALING ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                         Load Balancer                               │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐                │
│         │                    │                    │                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│  │  API Pod 1  │     │  API Pod 2  │     │  API Pod N  │          │
│  │             │     │             │     │             │          │
│  │  FastAPI    │     │  FastAPI    │     │  FastAPI    │          │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘          │
│         │                   │                   │                  │
│         └───────────────────┴───────────────────┘                  │
│                             │                                      │
│                             ▼                                      │
│                    ┌─────────────────┐                             │
│                    │  Redis Cluster  │  ← Shared State             │
│                    │  (Call State)   │    Session Affinity         │
│                    └─────────────────┘                             │
│                                                                     │
│  Scaling Triggers:                                                  │
│  • CPU > 70% for 5 minutes → Scale up                              │
│  • Active calls > 100 per pod → Scale up                           │
│  • Memory > 80% → Scale up                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Database Scaling (Future)

```
Current:   JSON file storage (demo/POC)
           └── call_records.json

Phase 2:   PostgreSQL (single instance)
           └── Supports ~10,000 calls/day

Phase 3:   PostgreSQL + Read Replicas
           ├── Primary (writes)
           └── Replicas (reads, analytics)
           └── Supports ~100,000 calls/day

Phase 4:   TimescaleDB (time-series optimized)
           ├── Automatic partitioning
           ├── Compression for old data
           └── Supports millions of calls
```

---

## 10. Deployment Pipeline

### 10.1 CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CI/CD PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │  Push   │───>│  Build  │───>│  Test   │───>│ Deploy  │         │
│  │  Code   │    │         │    │         │    │         │         │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘         │
│                                                                     │
│  GitHub Actions Workflow:                                           │
│  ────────────────────────                                           │
│                                                                     │
│  1. Code Push (develop branch)                                      │
│     │                                                               │
│     ▼                                                               │
│  2. Install Dependencies (npm ci)                                   │
│     │                                                               │
│     ▼                                                               │
│  3. Build Static Site (npm run build)                              │
│     │                                                               │
│     ▼                                                               │
│  4. Deploy via FTP (to Hostinger)                                  │
│     │                                                               │
│     ▼                                                               │
│  5. Deployment Complete ✓                                           │
│                                                                     │
│  Trigger: Push to 'develop' branch OR manual dispatch              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Environment Configuration

```bash
# .env.example

# Server
API_BASE_URL=https://your-domain.com
PORT=8000

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# Ultravox
ULTRAVOX_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Storage
CALL_RECORDS_FILE_PATH=./call_records.json

# Logging
LOG_LEVEL=INFO
```

---

## 11. Cost Analysis

### 11.1 Per-Call Cost Breakdown

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COST PER CALL (ESTIMATED)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Assuming: 3-minute average call duration                           │
│                                                                     │
│  Service            │ Unit Cost          │ Per Call Cost            │
│  ─────────────────────────────────────────────────────────────      │
│  Twilio Voice       │ $0.014/min         │ $0.042                   │
│  Ultravox AI        │ ~$0.01/min         │ $0.030                   │
│  OpenAI Analysis    │ $0.00015/1K tokens │ $0.005                   │
│  Infrastructure     │ ~$0.001/call       │ $0.001                   │
│  ─────────────────────────────────────────────────────────────      │
│  TOTAL              │                    │ ~$0.078/call             │
│                                                                     │
│  Volume Pricing (Monthly)                                           │
│  ────────────────────────                                           │
│  1,000 calls/month    → ~$78/month                                 │
│  10,000 calls/month   → ~$700/month (+ volume discounts)           │
│  100,000 calls/month  → ~$6,000/month (+ enterprise pricing)       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12. Future Roadmap

### Phase 1: Current (POC) ✓
- [x] Basic outbound/inbound calling
- [x] Real-time transcription
- [x] AI call analysis
- [x] Dashboard with analytics
- [x] File-based storage

### Phase 2: Production Ready
- [ ] PostgreSQL database
- [ ] User authentication (JWT)
- [ ] Multi-tenant support
- [ ] Webhook retry logic
- [ ] Call recording storage (S3)
- [ ] Advanced error handling

### Phase 3: Enterprise Features
- [ ] Custom voice training
- [ ] Multi-language support
- [ ] CRM integrations (Salesforce, HubSpot)
- [ ] Calendar integrations (Google, Outlook)
- [ ] Advanced analytics & reporting
- [ ] White-label solution

### Phase 4: AI Enhancements
- [ ] Intent detection & routing
- [ ] Automated follow-up scheduling
- [ ] Predictive analytics
- [ ] Voice cloning for brand consistency
- [ ] Real-time coaching for agents

---

## 13. Appendix

### A. Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend (Marketing) | Next.js 15, React 19, TailwindCSS | Product website |
| Frontend (Dashboard) | HTML5, CSS3, JavaScript | Admin interface |
| Backend | Python 3.11, FastAPI, Pydantic | API server |
| Voice AI | Ultravox | Real-time conversations |
| Telephony | Twilio | Phone connectivity |
| LLM | OpenAI GPT-4o-mini | Call analysis |
| Storage (POC) | JSON files | Call records |
| Storage (Prod) | PostgreSQL, Redis | Persistent data |
| Hosting (Web) | Hostinger | Static website |
| CI/CD | GitHub Actions | Automated deployment |

### B. API Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created (call initiated) |
| 400 | Bad request (validation error) |
| 404 | Resource not found |
| 500 | Internal server error |

### C. Call Status State Machine

```
PENDING → INITIATING → RINGING → IN_PROGRESS → COMPLETED
    │         │           │            │
    └─────────┴───────────┴────────────┴──→ FAILED
                          │
                          └──→ NO_ANSWER
                          │
                          └──→ BUSY
```

---

*Document Version: 1.0*
*Last Updated: February 2026*
*Author: Reapdat Engineering Team*
