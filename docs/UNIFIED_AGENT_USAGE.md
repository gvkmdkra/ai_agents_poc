# Unified AI Agent - Usage Guide

## Overview

The Unified AI Agent combines voice calling and chat capabilities into a single platform. This guide shows you how to set up, configure, and use the system.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [API Reference](#api-reference)
4. [Creating a Tenant](#creating-a-tenant)
5. [Using the Chat API](#using-the-chat-api)
6. [Using the Voice Calling API](#using-the-voice-calling-api)
7. [Widget Integration](#widget-integration)
8. [Authentication](#authentication)
9. [Webhooks](#webhooks)

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/gvkmdkra/ai_agents_poc.git
cd ai_agents_poc/unified_agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
- `OPENAI_API_KEY` - For LLM and embeddings
- `ULTRAVOX_API_KEY` - For voice AI
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` - For phone calls
- `PINECONE_API_KEY` - For vector search (RAG and Text-to-SQL)

### 3. Run the Server

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production with Docker
docker-compose up -d
```

### 4. Access the API

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ULTRAVOX_API_KEY` | Ultravox voice AI key | Yes (for voice) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | Yes (for phone) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Yes (for phone) |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number | Yes (for phone) |
| `PINECONE_API_KEY` | Pinecone API key | Yes |
| `PINECONE_INDEX_NAME` | Default Pinecone index | Yes |
| `DATABASE_TYPE` | turso, sqlite, or postgres | No (default: turso) |
| `TURSO_DATABASE_URL` | Turso database URL | If using Turso |
| `TURSO_AUTH_TOKEN` | Turso auth token | If using Turso |
| `SECRET_KEY` | JWT signing secret | Yes (production) |
| `API_BASE_URL` | Your API's public URL | Yes |

### Feature Flags

Enable/disable features via environment:

```bash
ENABLE_VOICE_CALLING=true
ENABLE_CHAT=true
ENABLE_TEXT_TO_SQL=true
ENABLE_RAG=true
ENABLE_LEAD_CAPTURE=true
ENABLE_ANALYTICS=true
```

---

## API Reference

### Base URL

Production: `https://your-domain.com/api/v1`
Local: `http://localhost:8000/api/v1`

### Authentication

Include your API key in every request:

```bash
# Header (recommended)
-H "X-API-Key: your-api-key"

# Bearer token
-H "Authorization: Bearer your-api-key"
```

For database access (Text-to-SQL), include a JWT token with `userid`:

```bash
-H "Authorization: Bearer your-jwt-token"
```

---

## Creating a Tenant

### 1. Create a Tenant (Admin API Key Required)

```bash
curl -X POST http://localhost:8000/api/v1/tenants/ \
  -H "X-API-Key: admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme",
    "system_prompt": "You are a helpful assistant for Acme Corporation. Help customers with product inquiries.",
    "welcome_message": "Hello! Welcome to Acme. How can I help you today?",
    "voice": "lily",
    "primary_color": "#4F46E5",
    "enable_voice_calling": true,
    "enable_chat": true,
    "enable_text_to_sql": true
  }'
```

Response:
```json
{
  "id": "tenant-uuid-here",
  "name": "Acme Corporation",
  "slug": "acme",
  "is_active": true,
  "enable_voice_calling": true,
  "enable_chat": true,
  "enable_text_to_sql": true,
  "enable_lead_capture": true,
  "created_at": "2026-02-03T19:00:00"
}
```

### 2. Create an API Key for the Tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants/{tenant_id}/api-keys \
  -H "X-API-Key: admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "can_call": true,
    "can_chat": true,
    "can_admin": false
  }'
```

Response:
```json
{
  "id": "key-uuid",
  "name": "Production Key",
  "key": "ua_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "is_active": true,
  "can_call": true,
  "can_chat": true,
  "can_admin": false,
  "created_at": "2026-02-03T19:00:00"
}
```

**Important**: Save the `key` value - it's only shown once!

---

## Using the Chat API

### Send a Message

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "X-API-Key: ua_your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many active clients do we have?",
    "tenant_id": "your-tenant-id",
    "session_id": null,
    "client_name": "John Doe"
  }'
```

Response:
```json
{
  "response": "Based on our records, you currently have 150 active clients.",
  "session_id": "abc123def456",
  "sources": [{"type": "database", "data": [{"count": 150}]}],
  "method": "database"
}
```

### Query Methods

The AI automatically routes queries to the appropriate method:

| Method | Description | Example Questions |
|--------|-------------|-------------------|
| `database` | Text-to-SQL for data queries | "How many users?", "Show client list" |
| `rag` | Document search | "What's our return policy?", "Company history" |
| `direct` | Conversational | "Hello", "Thank you" |
| `lead_capture` | Lead collection | "I'd like to be contacted" |

### Get Chat History

```bash
curl http://localhost:8000/api/v1/chat/history/{session_id} \
  -H "X-API-Key: ua_your-api-key"
```

---

## Using the Voice Calling API

### Browser-Based Voice Call (WebRTC)

```bash
curl -X POST http://localhost:8000/api/v1/calls/initiate \
  -H "X-API-Key: ua_your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "call_type": "browser",
    "client_name": "John Doe",
    "custom_prompt": "Help the customer with their order inquiry"
  }'
```

Response:
```json
{
  "success": true,
  "call_id": "call-uuid",
  "ultravox_call_id": "uv-call-id",
  "join_url": "wss://api.ultravox.ai/calls/xxx/join",
  "status": "initiated",
  "message": "Browser call initiated. Use join_url for WebRTC connection."
}
```

### Outbound Phone Call (Twilio)

```bash
curl -X POST http://localhost:8000/api/v1/calls/initiate \
  -H "X-API-Key: ua_your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "call_type": "outbound",
    "phone_number": "+1234567890",
    "client_name": "John Doe",
    "custom_prompt": "Follow up on the support ticket #12345"
  }'
```

### Get Call Status

```bash
curl http://localhost:8000/api/v1/calls/{call_id} \
  -H "X-API-Key: ua_your-api-key"
```

### End a Call

```bash
curl -X POST http://localhost:8000/api/v1/calls/{call_id}/end \
  -H "X-API-Key: ua_your-api-key"
```

### Get Call Analytics

```bash
curl "http://localhost:8000/api/v1/calls/dashboard/analytics?days=30" \
  -H "X-API-Key: ua_your-api-key"
```

---

## Widget Integration

### Get Widget Configuration

```bash
curl http://localhost:8000/api/v1/chat/widget/config/{tenant_id}
```

Response:
```json
{
  "tenant_id": "uuid",
  "tenant_name": "Acme Corporation",
  "welcome_message": "Hello! How can I help you?",
  "primary_color": "#4F46E5",
  "logo_url": "https://...",
  "enable_voice": true,
  "enable_chat": true
}
```

### Start Voice Call from Widget

```bash
curl -X POST "http://localhost:8000/api/v1/chat/widget/voice-call?tenant_id=xxx&client_name=John"
```

### JavaScript Widget Example

```html
<script>
  const TENANT_ID = "your-tenant-id";
  const API_URL = "https://your-api.com/api/v1";

  // Initialize chat
  async function initChat() {
    const config = await fetch(`${API_URL}/chat/widget/config/${TENANT_ID}`);
    return await config.json();
  }

  // Send message
  async function sendMessage(message, sessionId) {
    const response = await fetch(`${API_URL}/chat/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        tenant_id: TENANT_ID,
        session_id: sessionId,
        client_name: "Website Visitor"
      })
    });
    return await response.json();
  }

  // Start voice call
  async function startVoiceCall() {
    const response = await fetch(
      `${API_URL}/chat/widget/voice-call?tenant_id=${TENANT_ID}`,
      { method: "POST" }
    );
    const data = await response.json();
    // Connect to data.join_url using WebRTC
  }
</script>
```

---

## Authentication

### API Key Authentication

API keys are tied to tenants and have specific permissions:

| Permission | Description |
|------------|-------------|
| `can_call` | Make voice calls |
| `can_chat` | Use chat endpoints |
| `can_admin` | Manage tenants and keys |

### JWT Authentication (for Database Access)

For Text-to-SQL with user data isolation, include a JWT token:

```javascript
const jwt = require('jsonwebtoken');

const token = jwt.sign(
  { userid: 123 },  // User ID for data filtering
  'your-secret-key',
  { expiresIn: '24h' }
);

// Include in requests
fetch('/api/v1/chat/message', {
  headers: {
    'X-API-Key': 'ua_xxx',
    'Authorization': `Bearer ${token}`
  }
});
```

---

## Webhooks

### Twilio Webhooks

Configure these URLs in your Twilio console:

| Event | URL |
|-------|-----|
| Voice | `https://your-api.com/api/v1/webhooks/twilio/voice` |
| Status | `https://your-api.com/api/v1/webhooks/twilio/status` |

### Ultravox Webhooks

Configure in Ultravox dashboard:

| Event | URL |
|-------|-----|
| Status | `https://your-api.com/api/v1/webhooks/ultravox/status` |
| Transcript | `https://your-api.com/api/v1/webhooks/ultravox/transcript` |

---

## Deployment

### Docker Compose (Recommended)

```bash
cd unified_agent
docker-compose up -d
```

This starts:
- Unified Agent API (port 8000)
- Redis (for caching)
- Celery worker (for background tasks)

### Manual Deployment

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Environment-Specific Configuration

Create separate `.env` files:
- `.env.development`
- `.env.staging`
- `.env.production`

---

## Troubleshooting

### Health Check Failed

Check the detailed health endpoint:
```bash
curl http://localhost:8000/health/detailed
```

### Database Connection Issues

1. Verify `DATABASE_TYPE` is set correctly
2. Check Turso/SQLite credentials
3. Ensure database file is writable

### Voice Call Not Connecting

1. Verify Ultravox API key
2. Check Twilio credentials
3. Ensure webhook URLs are accessible

### Text-to-SQL Not Working

1. Verify Pinecone API key and index
2. Ensure view metadata is indexed
3. Check JWT token includes `userid`

---

## Support

For issues, please open a GitHub issue at:
https://github.com/gvkmdkra/ai_agents_poc/issues

---

*Documentation Version: 1.0*
*Last Updated: February 3, 2026*
