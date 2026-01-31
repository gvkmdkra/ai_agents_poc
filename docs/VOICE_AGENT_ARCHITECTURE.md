# AI Voice Agent Architecture

## End-to-End Technical Architecture
### Twilio + Ultravox + OpenAI + Odoo CRM Integration

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Deep Dive](#component-deep-dive)
4. [Multi-Tenant Design](#multi-tenant-design)
5. [Call Flow](#call-flow)
6. [Lead Management Pipeline](#lead-management-pipeline)
7. [Integration Specifications](#integration-specifications)
8. [Database Schema](#database-schema)
9. [API Specifications](#api-specifications)
10. [Deployment Architecture](#deployment-architecture)

---

## 1. System Overview

### Purpose
A multi-tenant AI Voice Agent platform that:
- Handles inbound/outbound calls with human-like conversation
- Captures leads and qualifies them (Hot/Warm/Cold)
- Integrates with Odoo CRM for lead management
- Supports WhatsApp and Email communications
- Schedules appointments with reminders and follow-ups
- Escalates to human agents when needed
- Configurable per-client with unique Twilio numbers

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Voice Gateway** | Twilio Programmable Voice | Phone numbers, call routing, WebRTC |
| **Voice AI Engine** | Ultravox | Real-time voice-to-voice AI |
| **LLM Backend** | OpenAI GPT-4o / GPT-4o-mini | Conversation intelligence |
| **CRM** | Odoo | Lead management, pipeline tracking |
| **Messaging** | Twilio WhatsApp, SendGrid | Multi-channel communication |
| **Orchestration** | LangGraph | Stateful conversation workflows |
| **Database** | PostgreSQL | Multi-tenant data storage |
| **Cache** | Redis | Session state, rate limiting |
| **Queue** | Redis Bull / Celery | Async tasks, reminders |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL CHANNELS                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │   Phone      │    │   WhatsApp   │    │    Email     │    │   Web Chat   │     │
│   │   (Twilio)   │    │   (Twilio)   │    │  (SendGrid)  │    │  (WebSocket) │     │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│          │                   │                   │                   │              │
└──────────┼───────────────────┼───────────────────┼───────────────────┼──────────────┘
           │                   │                   │                   │
           ▼                   ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (FastAPI)                                   │
│                                   Port 8000                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │ /webhook/voice  │  │ /webhook/whatsapp│ │ /webhook/email  │  │ /api/v1/chat   │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘ │
│           │                    │                    │                   │           │
│           └────────────────────┴────────────────────┴───────────────────┘           │
│                                         │                                            │
│                                         ▼                                            │
│                          ┌──────────────────────────┐                               │
│                          │   TENANT ROUTER          │                               │
│                          │   (Phone → Client Map)   │                               │
│                          └────────────┬─────────────┘                               │
└───────────────────────────────────────┼─────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              VOICE AI ENGINE                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                           ULTRAVOX INTEGRATION                                  │ │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │ │
│  │  │  ASR Engine  │───▶│  LLM Router  │───▶│  TTS Engine  │                      │ │
│  │  │  (Speech→Text)│    │  (OpenAI)    │    │  (Text→Speech)│                     │ │
│  │  └──────────────┘    └──────┬───────┘    └──────────────┘                      │ │
│  │                             │                                                   │ │
│  │                             ▼                                                   │ │
│  │                    ┌──────────────────┐                                        │ │
│  │                    │  Context Manager │                                        │ │
│  │                    │  (Conversation   │                                        │ │
│  │                    │   State Machine) │                                        │ │
│  │                    └────────┬─────────┘                                        │ │
│  └─────────────────────────────┼──────────────────────────────────────────────────┘ │
│                                │                                                     │
└────────────────────────────────┼─────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH ORCHESTRATOR                                     │
│                                 Port 9000                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │ Conversation │   │    Lead      │   │  Appointment │   │   Escalation │         │
│  │    Agent     │   │  Qualifier   │   │   Scheduler  │   │    Handler   │         │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘         │
│         │                  │                  │                  │                  │
│         └──────────────────┴──────────────────┴──────────────────┘                  │
│                                    │                                                 │
│                                    ▼                                                 │
│                        ┌───────────────────────┐                                    │
│                        │   WORKFLOW ENGINE     │                                    │
│                        │   (State Transitions) │                                    │
│                        └───────────┬───────────┘                                    │
│                                    │                                                 │
└────────────────────────────────────┼─────────────────────────────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   ODOO CRM       │    │   NOTIFICATION   │    │    SCHEDULER     │
│   INTEGRATION    │    │     SERVICE      │    │     SERVICE      │
├──────────────────┤    ├──────────────────┤    ├──────────────────┤
│ • Create Lead    │    │ • WhatsApp Msg   │    │ • Appointments   │
│ • Update Stage   │    │ • Email Send     │    │ • Reminders      │
│ • Add Notes      │    │ • SMS Alerts     │    │ • Follow-ups     │
│ • Assign Owner   │    │ • Push Notify    │    │ • Callbacks      │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐              │
│  │   PostgreSQL     │    │      Redis       │    │   File Storage   │              │
│  │   (Primary DB)   │    │   (Cache/Queue)  │    │   (S3/Minio)     │              │
│  ├──────────────────┤    ├──────────────────┤    ├──────────────────┤              │
│  │ • Tenants        │    │ • Session State  │    │ • Call Records   │              │
│  │ • Leads          │    │ • Rate Limits    │    │ • Transcripts    │              │
│  │ • Calls          │    │ • Task Queue     │    │ • Voice Files    │              │
│  │ • Appointments   │    │ • Real-time Data │    │ • Documents      │              │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Deep Dive

### 3.1 Twilio Voice Gateway

```python
# Call Flow Configuration
TWILIO_CONFIG = {
    "voice": {
        "answer_url": "/webhook/voice/answer",      # Incoming call handler
        "status_callback": "/webhook/voice/status", # Call status updates
        "recording_callback": "/webhook/voice/recording",
        "transcription_callback": "/webhook/voice/transcription",
        "fallback_url": "/webhook/voice/fallback",
    },
    "media_stream": {
        "url": "wss://your-domain.com/media-stream",
        "track": "both_tracks",  # inbound + outbound audio
    }
}
```

**Key Capabilities:**
- Programmable Voice for inbound/outbound calls
- Media Streams for real-time audio (WebSocket)
- Conference for warm transfers to human agents
- Recording with transcription
- DTMF handling for menu navigation

### 3.2 Ultravox Voice AI

Ultravox provides real-time voice-to-voice AI with:
- **Sub-200ms latency** for natural conversation
- **Streaming ASR** (Automatic Speech Recognition)
- **Neural TTS** with voice cloning
- **Turn-taking detection** for natural interruptions

```python
ULTRAVOX_CONFIG = {
    "model": "fixie-ai/ultravox-v0.4",
    "voice": {
        "provider": "elevenlabs",  # or "playht", "azure"
        "voice_id": "custom_cloned_voice",
        "language": "en-US",  # Configurable per tenant
    },
    "asr": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "en-US",
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-realtime",
        "temperature": 0.7,
    },
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
    }
}
```

### 3.3 OpenAI Integration

```python
OPENAI_CONFIG = {
    "conversation_model": "gpt-4o",          # Primary conversation
    "realtime_model": "gpt-4o-realtime",     # Voice-native model
    "classification_model": "gpt-4o-mini",   # Lead qualification
    "embedding_model": "text-embedding-3-small",

    "system_prompts": {
        "conversation": "industry_specific_prompt",
        "qualification": "lead_scoring_prompt",
        "appointment": "scheduling_prompt",
    }
}
```

### 3.4 Odoo CRM Integration

```python
ODOO_CONFIG = {
    "url": "https://your-odoo.com",
    "db": "production",
    "api_version": "v2",
    "endpoints": {
        "leads": "/api/v2/crm.lead",
        "contacts": "/api/v2/res.partner",
        "activities": "/api/v2/mail.activity",
        "calendar": "/api/v2/calendar.event",
    },
    "field_mapping": {
        "name": "lead_name",
        "phone": "phone",
        "email": "email_from",
        "company": "partner_name",
        "source": "source_id",
        "stage": "stage_id",
        "priority": "priority",  # 0=Low, 1=Medium, 2=High, 3=Very High
        "notes": "description",
    }
}
```

---

## 4. Multi-Tenant Design

### 4.1 Tenant Configuration Model

```python
class TenantConfig:
    """Per-client configuration"""

    # Identity
    tenant_id: UUID
    company_name: str
    industry: str  # healthcare, real_estate, insurance, etc.

    # Twilio Numbers (multiple per tenant)
    phone_numbers: List[PhoneNumber]
    whatsapp_numbers: List[PhoneNumber]

    # Voice AI Settings
    language: str  # en-US, es-ES, fr-FR, etc.
    voice_id: str  # Custom voice clone ID
    accent: str    # neutral, british, australian

    # Business Hours
    timezone: str
    business_hours: Dict[str, TimeRange]
    after_hours_action: str  # voicemail, transfer, callback

    # AI Personality
    agent_name: str
    greeting_script: str
    industry_knowledge_base: str
    faq_document_id: str

    # Lead Configuration
    qualification_criteria: Dict
    hot_lead_threshold: float
    warm_lead_threshold: float

    # CRM Integration
    odoo_url: str
    odoo_api_key: str
    lead_owner_id: int
    default_sales_team_id: int

    # Escalation Rules
    escalation_triggers: List[str]
    human_agents: List[HumanAgent]
    max_ai_attempts: int

    # Notifications
    notification_emails: List[str]
    whatsapp_notifications: bool
    sms_notifications: bool
```

### 4.2 Phone Number Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHONE NUMBER ROUTING TABLE                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ Phone Number    │ Tenant ID       │ Configuration               │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ +1-800-555-0001 │ tenant_realestate│ Real Estate Agent Voice    │
│ +1-800-555-0002 │ tenant_insurance │ Insurance Agent Voice      │
│ +1-800-555-0003 │ tenant_healthcare│ Healthcare Receptionist    │
│ +1-800-555-0004 │ tenant_legal     │ Legal Intake Specialist    │
│ +44-800-555-0005│ tenant_realestate│ UK Real Estate (British)   │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

---

## 5. Call Flow

### 5.1 Inbound Call Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              INBOUND CALL FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

     CALLER                    TWILIO                      VOICE AI
       │                         │                            │
       │  ①  Dials Number        │                            │
       │ ──────────────────────▶ │                            │
       │                         │                            │
       │                         │  ②  Webhook: /voice/answer │
       │                         │ ──────────────────────────▶│
       │                         │                            │
       │                         │     ③  Lookup Tenant       │
       │                         │     by Phone Number        │
       │                         │                            │
       │                         │  ④  TwiML: <Stream>        │
       │                         │ ◀──────────────────────────│
       │                         │                            │
       │  ⑤  Media Stream        │                            │
       │     (WebSocket)         │                            │
       │ ◀─────────────────────▶ │ ◀─────────────────────────▶│
       │                         │                            │
       │                         │  ⑥  Ultravox Session       │
       │                         │     Initialized            │
       │                         │                            │
       │  ⑦  AI Greeting         │                            │
       │ ◀──────────────────────────────────────────────────── │
       │  "Hello! Thank you for  │                            │
       │   calling ABC Realty.   │                            │
       │   I'm Sarah, how may I  │                            │
       │   help you today?"      │                            │
       │                         │                            │
       │  ⑧  Caller Speaks       │                            │
       │ ────────────────────────────────────────────────────▶ │
       │  "I'm looking to buy    │                            │
       │   a house in downtown"  │                            │  ⑨  ASR + LLM
       │                         │                            │     Processing
       │                         │                            │
       │  ⑩  AI Response         │                            │
       │ ◀──────────────────────────────────────────────────── │
       │  "That's wonderful!     │                            │
       │   What's your budget    │                            │
       │   range and preferred   │                            │
       │   number of bedrooms?"  │                            │
       │                         │                            │
       │         ... CONVERSATION CONTINUES ...                │
       │                         │                            │
       │  ⑪  Lead Qualification  │                            │
       │     Triggers            │                            │
       │                         │                            ├──────────────┐
       │                         │                            │  Classify:   │
       │                         │                            │  HOT LEAD    │
       │                         │                            ├──────────────┘
       │                         │                            │
       │                         │                            │  ⑫  Create Lead
       │                         │                            │     in Odoo CRM
       │                         │                            │ ───────────────▶
       │                         │                            │
       │  ⑬  Appointment         │                            │
       │     Scheduling          │                            │
       │ ◀──────────────────────────────────────────────────── │
       │  "I can schedule a      │                            │
       │   viewing for you.      │                            │
       │   How about tomorrow    │                            │
       │   at 2 PM?"             │                            │
       │                         │                            │
       │  ⑭  Confirmation        │                            │
       │ ────────────────────────────────────────────────────▶ │
       │  "Yes, that works"      │                            │
       │                         │                            │
       │                         │                            │  ⑮  Create
       │                         │                            │     Appointment
       │                         │                            │ ───────────────▶
       │                         │                            │
       │  ⑯  Call End            │                            │
       │ ◀──────────────────────────────────────────────────── │
       │  "Perfect! I've sent    │                            │
       │   you a confirmation    │                            │
       │   via WhatsApp..."      │                            │
       │                         │                            │  ⑰  Send
       │                         │                            │     Notifications
       │                         │                            │ ───────────────▶
       │                         │                            │  • WhatsApp
       │                         │                            │  • Email
       │                         │                            │  • Calendar Invite
       ▼                         ▼                            ▼
```

### 5.2 Human Escalation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           HUMAN ESCALATION TRIGGERS                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  AUTOMATIC TRIGGERS:                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │ • Caller explicitly requests human agent ("speak to a person")                 │ │
│  │ • Sentiment score drops below threshold (frustration detected)                 │ │
│  │ • AI confidence score below 0.6 for 3+ consecutive turns                      │ │
│  │ • Complex legal/compliance questions detected                                  │ │
│  │ • Caller mentions competitor pricing (high-value negotiation)                 │ │
│  │ • Emergency keywords detected (safety, urgent medical, etc.)                  │ │
│  │ • Max AI conversation turns reached (configurable per tenant)                 │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
│  ESCALATION PROCESS:                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Trigger    │───▶│  Check      │───▶│  Warm       │───▶│  Conference │          │
│  │  Detected   │    │  Agent      │    │  Transfer   │    │  Bridge     │          │
│  │             │    │  Available  │    │  Intro      │    │  Handoff    │          │
│  └─────────────┘    └──────┬──────┘    └─────────────┘    └─────────────┘          │
│                            │                                                         │
│                            ▼ (No Agent Available)                                    │
│                    ┌─────────────┐    ┌─────────────┐                               │
│                    │  Schedule   │───▶│  Send       │                               │
│                    │  Callback   │    │  Notify     │                               │
│                    └─────────────┘    └─────────────┘                               │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Lead Management Pipeline

### 6.1 Lead Qualification Algorithm

```python
class LeadQualifier:
    """
    BANT Framework + AI Scoring
    - Budget: Financial capacity signals
    - Authority: Decision-maker identification
    - Need: Problem/pain point clarity
    - Timeline: Purchase urgency
    """

    SCORING_WEIGHTS = {
        "budget_mentioned": 0.25,
        "decision_maker": 0.20,
        "clear_need": 0.25,
        "timeline_urgent": 0.20,
        "engagement_score": 0.10,
    }

    THRESHOLDS = {
        "hot": 0.75,   # Score >= 0.75 → Hot Lead (immediate action)
        "warm": 0.45,  # Score 0.45-0.74 → Warm Lead (nurture)
        "cold": 0.0,   # Score < 0.45 → Cold Lead (long-term)
    }
```

### 6.2 Lead Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              LEAD LIFECYCLE                                          │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │   NEW    │────▶│QUALIFIED │────▶│CONTACTED │────▶│ MEETING  │────▶│  CLOSED  │
  │          │     │          │     │          │     │ SCHEDULED│     │  (Won)   │
  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └──────────┘
       │                │                │                │                │
       │                │                │                │                ▼
       │                │                │                │           ┌──────────┐
       │                │                │                └──────────▶│  CLOSED  │
       │                │                │                            │  (Lost)  │
       │                │                │                            └──────────┘
       │                │                │
       ▼                ▼                ▼
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                           AUTOMATED ACTIONS                                      │
  ├─────────────────────────────────────────────────────────────────────────────────┤
  │                                                                                  │
  │  NEW → QUALIFIED:                                                                │
  │  • AI qualification call/chat completed                                          │
  │  • Lead score calculated                                                         │
  │  • Hot/Warm/Cold classification assigned                                         │
  │                                                                                  │
  │  QUALIFIED → CONTACTED:                                                          │
  │  • Human agent assigned (hot leads)                                              │
  │  • Follow-up email sent (warm leads)                                             │
  │  • Added to nurture sequence (cold leads)                                        │
  │                                                                                  │
  │  CONTACTED → MEETING SCHEDULED:                                                  │
  │  • Calendar event created                                                        │
  │  • WhatsApp confirmation sent                                                    │
  │  • Reminder scheduled (24h, 1h before)                                           │
  │                                                                                  │
  │  MEETING → CLOSED:                                                               │
  │  • Post-meeting feedback collected                                               │
  │  • Next steps defined                                                            │
  │  • Deal value updated in CRM                                                     │
  │                                                                                  │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Follow-up Automation

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         FOLLOW-UP SEQUENCE BY LEAD TYPE                              │
└─────────────────────────────────────────────────────────────────────────────────────┘

HOT LEADS (Score ≥ 0.75):
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ T+0     │──▶│ T+1h    │──▶│ T+24h   │──▶│ T+48h   │──▶│ T+7d    │
│WhatsApp │   │ Human   │   │ Email + │   │ AI Call │   │ Final   │
│Confirm  │   │ Call    │   │ SMS     │   │ Check-in│   │ Attempt │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘

WARM LEADS (Score 0.45-0.74):
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ T+0     │──▶│ T+24h   │──▶│ T+3d    │──▶│ T+7d    │──▶│ T+14d   │
│ Email   │   │ AI Call │   │ Value   │   │ Case    │   │ Special │
│ Summary │   │ Nurture │   │ Content │   │ Study   │   │ Offer   │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘

COLD LEADS (Score < 0.45):
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ T+0     │──▶│ T+7d    │──▶│ T+30d   │──▶│ T+60d   │──▶│ T+90d   │
│ Email   │   │ News-   │   │ Re-eng- │   │ Survey  │   │ Archive │
│ Thanks  │   │ letter  │   │ agement │   │ Request │   │ or Wake │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

---

## 7. Integration Specifications

### 7.1 Twilio Webhooks

```yaml
# Webhook Endpoints
webhooks:
  voice:
    answer:
      method: POST
      url: /webhook/voice/answer
      params: [CallSid, From, To, Direction, CallStatus]
      response: TwiML

    status:
      method: POST
      url: /webhook/voice/status
      params: [CallSid, CallStatus, CallDuration, RecordingUrl]

    recording:
      method: POST
      url: /webhook/voice/recording
      params: [RecordingSid, RecordingUrl, RecordingDuration]

    transcription:
      method: POST
      url: /webhook/voice/transcription
      params: [TranscriptionSid, TranscriptionText, TranscriptionStatus]

  whatsapp:
    incoming:
      method: POST
      url: /webhook/whatsapp/incoming
      params: [From, Body, MediaUrl, ProfileName]

    status:
      method: POST
      url: /webhook/whatsapp/status
      params: [MessageSid, MessageStatus, ErrorCode]

  sms:
    incoming:
      method: POST
      url: /webhook/sms/incoming
      params: [From, Body, To]
```

### 7.2 Odoo CRM API

```yaml
# Odoo XML-RPC / REST API Integration
odoo:
  authentication:
    method: api_key  # or oauth2
    header: X-API-Key

  endpoints:
    create_lead:
      method: POST
      path: /api/v2/crm.lead
      payload:
        name: string          # Lead name
        phone: string         # Phone number
        email_from: string    # Email address
        partner_name: string  # Company name
        description: string   # Notes/transcript
        source_id: integer    # Lead source (AI Voice)
        stage_id: integer     # Pipeline stage
        priority: string      # 0-3 (cold to hot)
        user_id: integer      # Assigned salesperson
        team_id: integer      # Sales team
        x_lead_score: float   # Custom: AI lead score
        x_call_transcript: text  # Custom: Full transcript

    update_lead:
      method: PUT
      path: /api/v2/crm.lead/{id}

    create_activity:
      method: POST
      path: /api/v2/mail.activity
      payload:
        res_model: crm.lead
        res_id: integer       # Lead ID
        activity_type_id: integer  # Call, Meeting, Email
        summary: string       # Activity title
        date_deadline: date   # Due date
        user_id: integer      # Assigned to

    create_calendar_event:
      method: POST
      path: /api/v2/calendar.event
      payload:
        name: string          # Event title
        start: datetime       # Start time
        stop: datetime        # End time
        partner_ids: list     # Attendees
        description: string   # Event details
        location: string      # Meeting location
        reminder_ids: list    # Reminder settings
```

### 7.3 Ultravox Real-time API

```yaml
# Ultravox WebSocket Protocol
ultravox:
  connection:
    url: wss://api.ultravox.ai/v1/realtime
    headers:
      Authorization: Bearer {api_key}
      X-Tenant-ID: {tenant_id}

  events:
    # Client → Server
    session.create:
      model: string
      voice: object
      system_prompt: string
      tools: array

    audio.input:
      audio: base64
      encoding: pcm_s16le
      sample_rate: 16000

    conversation.interrupt:
      reason: string

    # Server → Client
    session.created:
      session_id: string

    audio.output:
      audio: base64
      encoding: pcm_s16le
      sample_rate: 24000

    transcript.partial:
      text: string
      role: user|assistant

    transcript.final:
      text: string
      role: user|assistant

    tool.call:
      name: string
      arguments: object

    session.ended:
      reason: string
      duration_ms: integer
```

---

## 8. Database Schema

```sql
-- =====================================================
-- MULTI-TENANT VOICE AGENT DATABASE SCHEMA
-- =====================================================

-- Tenants (Clients)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    industry VARCHAR(50) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    status VARCHAR(20) DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Phone Numbers (Multi-tenant)
CREATE TABLE phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    phone_type VARCHAR(20) NOT NULL, -- voice, whatsapp, sms
    twilio_sid VARCHAR(50),
    display_name VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en-US',
    voice_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_phone_numbers_lookup ON phone_numbers(phone_number, is_active);

-- Tenant Voice Configuration
CREATE TABLE tenant_voice_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL,
    greeting_script TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    voice_provider VARCHAR(50) DEFAULT 'elevenlabs',
    voice_id VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en-US',
    accent VARCHAR(50),
    speaking_rate FLOAT DEFAULT 1.0,
    pitch FLOAT DEFAULT 1.0,
    industry_knowledge_base TEXT,
    faq_embeddings_id VARCHAR(100),
    escalation_keywords TEXT[],
    max_conversation_turns INTEGER DEFAULT 50,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Business Hours
CREATE TABLE business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL, -- 0=Sunday, 6=Saturday
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN DEFAULT false,
    after_hours_action VARCHAR(50) DEFAULT 'voicemail'
);

-- Leads
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,

    -- Contact Info
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(255),
    company_name VARCHAR(255),

    -- Lead Scoring
    lead_score FLOAT DEFAULT 0.0,
    lead_temperature VARCHAR(10), -- hot, warm, cold
    qualification_data JSONB DEFAULT '{}',

    -- Source Tracking
    source VARCHAR(50), -- inbound_call, outbound_call, whatsapp, web
    source_phone_number VARCHAR(20),
    utm_source VARCHAR(100),
    utm_campaign VARCHAR(100),

    -- CRM Sync
    odoo_lead_id INTEGER,
    odoo_sync_status VARCHAR(20) DEFAULT 'pending',
    odoo_last_sync TIMESTAMPTZ,

    -- Status
    status VARCHAR(50) DEFAULT 'new',
    assigned_to UUID,

    -- Metadata
    tags TEXT[],
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_tenant ON leads(tenant_id, status);
CREATE INDEX idx_leads_phone ON leads(phone);
CREATE INDEX idx_leads_temperature ON leads(tenant_id, lead_temperature);

-- Calls
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),

    -- Twilio Data
    twilio_call_sid VARCHAR(50) UNIQUE,
    direction VARCHAR(20), -- inbound, outbound
    from_number VARCHAR(20),
    to_number VARCHAR(20),

    -- Call Metrics
    status VARCHAR(30),
    duration_seconds INTEGER,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,

    -- AI Conversation
    conversation_turns INTEGER DEFAULT 0,
    ai_handled BOOLEAN DEFAULT true,
    escalated_to_human BOOLEAN DEFAULT false,
    escalation_reason VARCHAR(255),

    -- Recordings
    recording_url TEXT,
    recording_duration INTEGER,

    -- Transcript
    transcript JSONB DEFAULT '[]',
    transcript_summary TEXT,

    -- Analysis
    sentiment_score FLOAT,
    intent_detected TEXT[],
    entities_extracted JSONB DEFAULT '{}',

    -- Outcomes
    outcome VARCHAR(50), -- qualified, appointment_set, callback_requested, etc.
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calls_tenant_date ON calls(tenant_id, started_at DESC);
CREATE INDEX idx_calls_twilio ON calls(twilio_call_sid);

-- Appointments
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),
    call_id UUID REFERENCES calls(id),

    -- Scheduling
    title VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    timezone VARCHAR(50),
    location VARCHAR(255),
    meeting_type VARCHAR(50), -- in_person, phone, video
    meeting_link TEXT,

    -- Participants
    assigned_agent_id UUID,
    agent_name VARCHAR(100),
    agent_email VARCHAR(255),

    -- Status
    status VARCHAR(30) DEFAULT 'scheduled', -- scheduled, confirmed, completed, cancelled, no_show
    confirmation_sent BOOLEAN DEFAULT false,
    reminder_sent_24h BOOLEAN DEFAULT false,
    reminder_sent_1h BOOLEAN DEFAULT false,

    -- CRM Sync
    odoo_event_id INTEGER,
    odoo_activity_id INTEGER,
    google_calendar_event_id VARCHAR(100),

    -- Notes
    notes TEXT,
    outcome TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_appointments_tenant_date ON appointments(tenant_id, scheduled_at);
CREATE INDEX idx_appointments_status ON appointments(status, scheduled_at);

-- Notifications / Messages
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),

    -- Message Details
    channel VARCHAR(20) NOT NULL, -- whatsapp, sms, email
    direction VARCHAR(20), -- outbound, inbound
    to_address VARCHAR(255),
    from_address VARCHAR(255),
    subject VARCHAR(255),
    body TEXT,
    template_id VARCHAR(100),
    template_data JSONB,

    -- Delivery Status
    status VARCHAR(30) DEFAULT 'pending',
    external_id VARCHAR(100), -- Twilio SID, SendGrid ID
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    error_message TEXT,

    -- Scheduling
    scheduled_for TIMESTAMPTZ,
    notification_type VARCHAR(50), -- confirmation, reminder, follow_up

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_tenant ON notifications(tenant_id, created_at DESC);
CREATE INDEX idx_notifications_scheduled ON notifications(scheduled_for, status) WHERE status = 'pending';

-- Follow-up Tasks
CREATE TABLE follow_up_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),

    -- Task Details
    task_type VARCHAR(50), -- call, email, whatsapp, sms
    title VARCHAR(255),
    description TEXT,

    -- Scheduling
    scheduled_for TIMESTAMPTZ NOT NULL,
    sequence_step INTEGER, -- Position in follow-up sequence
    sequence_id VARCHAR(100), -- Group related follow-ups

    -- Execution
    status VARCHAR(30) DEFAULT 'pending',
    executed_at TIMESTAMPTZ,
    result JSONB,

    -- Assignment
    assigned_to UUID,
    is_ai_task BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_follow_ups_pending ON follow_up_tasks(scheduled_for, status) WHERE status = 'pending';

-- Human Agents
CREATE TABLE human_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),

    -- Availability
    is_available BOOLEAN DEFAULT true,
    availability_hours JSONB DEFAULT '{}',
    max_concurrent_calls INTEGER DEFAULT 3,
    current_call_count INTEGER DEFAULT 0,

    -- Skills/Routing
    skills TEXT[],
    languages TEXT[],
    priority INTEGER DEFAULT 0,

    -- Stats
    total_calls_handled INTEGER DEFAULT 0,
    avg_call_duration INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation Sessions (for context)
CREATE TABLE conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),
    call_id UUID REFERENCES calls(id),

    -- Session State
    channel VARCHAR(20), -- voice, whatsapp, web
    state JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',

    -- LangGraph Checkpoint
    langgraph_thread_id VARCHAR(100),
    checkpoint_data BYTEA,

    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- Analytics Events
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    lead_id UUID,
    call_id UUID,

    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_tenant_type ON analytics_events(tenant_id, event_type, created_at DESC);

-- =====================================================
-- VIEWS
-- =====================================================

-- Active calls view
CREATE VIEW active_calls AS
SELECT c.*, t.name as tenant_name, l.first_name, l.last_name, l.lead_temperature
FROM calls c
JOIN tenants t ON c.tenant_id = t.id
LEFT JOIN leads l ON c.lead_id = l.id
WHERE c.status IN ('ringing', 'in-progress');

-- Today's appointments view
CREATE VIEW todays_appointments AS
SELECT a.*, t.name as tenant_name, l.first_name, l.last_name, l.phone, l.email
FROM appointments a
JOIN tenants t ON a.tenant_id = t.id
LEFT JOIN leads l ON a.lead_id = l.id
WHERE DATE(a.scheduled_at AT TIME ZONE t.timezone) = CURRENT_DATE
ORDER BY a.scheduled_at;

-- Lead conversion funnel
CREATE VIEW lead_funnel AS
SELECT
    tenant_id,
    lead_temperature,
    status,
    COUNT(*) as count,
    AVG(lead_score) as avg_score
FROM leads
GROUP BY tenant_id, lead_temperature, status;
```

---

## 9. API Specifications

### 9.1 Voice Webhook Endpoints

```yaml
openapi: 3.0.0
info:
  title: AI Voice Agent API
  version: 1.0.0

paths:
  /webhook/voice/answer:
    post:
      summary: Handle incoming voice call
      requestBody:
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              properties:
                CallSid:
                  type: string
                From:
                  type: string
                To:
                  type: string
                Direction:
                  type: string
                CallStatus:
                  type: string
      responses:
        '200':
          description: TwiML response
          content:
            application/xml:
              schema:
                type: string
              example: |
                <?xml version="1.0" encoding="UTF-8"?>
                <Response>
                  <Connect>
                    <Stream url="wss://api.example.com/media-stream">
                      <Parameter name="tenant_id" value="abc123"/>
                    </Stream>
                  </Connect>
                </Response>

  /webhook/voice/status:
    post:
      summary: Handle call status updates
      requestBody:
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              properties:
                CallSid:
                  type: string
                CallStatus:
                  type: string
                CallDuration:
                  type: integer
      responses:
        '200':
          description: Status acknowledged

  /api/v1/calls/outbound:
    post:
      summary: Initiate outbound AI call
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required:
                - tenant_id
                - to_number
              properties:
                tenant_id:
                  type: string
                  format: uuid
                to_number:
                  type: string
                lead_id:
                  type: string
                  format: uuid
                campaign_id:
                  type: string
                script_override:
                  type: string
      responses:
        '200':
          description: Call initiated
          content:
            application/json:
              schema:
                type: object
                properties:
                  call_id:
                    type: string
                  twilio_call_sid:
                    type: string
                  status:
                    type: string

  /api/v1/leads:
    post:
      summary: Create new lead
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LeadCreate'
      responses:
        '201':
          description: Lead created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Lead'

    get:
      summary: List leads
      parameters:
        - name: tenant_id
          in: query
          required: true
          schema:
            type: string
        - name: temperature
          in: query
          schema:
            type: string
            enum: [hot, warm, cold]
        - name: status
          in: query
          schema:
            type: string
      responses:
        '200':
          description: List of leads
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Lead'

  /api/v1/appointments:
    post:
      summary: Schedule appointment
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AppointmentCreate'
      responses:
        '201':
          description: Appointment created

components:
  schemas:
    LeadCreate:
      type: object
      required:
        - tenant_id
        - phone
      properties:
        tenant_id:
          type: string
          format: uuid
        first_name:
          type: string
        last_name:
          type: string
        phone:
          type: string
        email:
          type: string
        company_name:
          type: string
        source:
          type: string
        custom_fields:
          type: object

    Lead:
      allOf:
        - $ref: '#/components/schemas/LeadCreate'
        - type: object
          properties:
            id:
              type: string
              format: uuid
            lead_score:
              type: number
            lead_temperature:
              type: string
            status:
              type: string
            created_at:
              type: string
              format: date-time

    AppointmentCreate:
      type: object
      required:
        - tenant_id
        - lead_id
        - scheduled_at
      properties:
        tenant_id:
          type: string
          format: uuid
        lead_id:
          type: string
          format: uuid
        title:
          type: string
        scheduled_at:
          type: string
          format: date-time
        duration_minutes:
          type: integer
        meeting_type:
          type: string
          enum: [in_person, phone, video]
        location:
          type: string
        notes:
          type: string
```

---

## 10. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION DEPLOYMENT                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   CloudFlare    │
                              │   (CDN + WAF)   │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  Load Balancer  │
                              │   (AWS ALB)     │
                              └────────┬────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   API Server     │      │   API Server     │      │   API Server     │
│   (FastAPI)      │      │   (FastAPI)      │      │   (FastAPI)      │
│   Container #1   │      │   Container #2   │      │   Container #3   │
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   Internal Load Balancer │
                    └────────────┬─────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  LangGraph Svc   │  │  LangGraph Svc   │  │   WebSocket      │
│  (Orchestrator)  │  │  (Orchestrator)  │  │   Gateway        │
│  Container #1    │  │  Container #2    │  │   (Media Stream) │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL     │  │      Redis       │  │   Celery Worker  │
│   (RDS)          │  │   (ElastiCache)  │  │   (Background)   │
│   Primary +      │  │   Cluster Mode   │  │   Tasks x3       │
│   Read Replicas  │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘

                    EXTERNAL SERVICES
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Twilio  │  │Ultravox │  │ OpenAI  │  │  Odoo   │            │
│  │  API    │  │   API   │  │   API   │  │   API   │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │SendGrid │  │  S3     │  │LangSmith│                         │
│  │  Email  │  │ Storage │  │ Tracing │                         │
│  └─────────┘  └─────────┘  └─────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  api-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/voiceagent
      - REDIS_URL=redis://redis:6379
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
      - ULTRAVOX_API_KEY=${ULTRAVOX_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ODOO_URL=${ODOO_URL}
      - ODOO_API_KEY=${ODOO_API_KEY}
    depends_on:
      - db
      - redis

  langgraph-server:
    build:
      context: .
      dockerfile: Dockerfile.langgraph
    ports:
      - "9000:9000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/voiceagent
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  websocket-gateway:
    build:
      context: .
      dockerfile: Dockerfile.websocket
    ports:
      - "8080:8080"
    environment:
      - ULTRAVOX_API_KEY=${ULTRAVOX_API_KEY}

  celery-worker:
    build: .
    command: celery -A src.tasks worker -l info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/voiceagent
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A src.tasks beat -l info
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=voiceagent
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## Summary

This architecture provides:

1. **Multi-Tenant Isolation**: Each client has dedicated phone numbers, voice configurations, and CRM settings
2. **Human-Like Conversations**: Ultravox + OpenAI for natural, low-latency voice interactions
3. **Intelligent Lead Management**: AI-powered qualification with Hot/Warm/Cold classification
4. **Seamless CRM Integration**: Real-time sync with Odoo for leads, activities, and appointments
5. **Omnichannel Communication**: Voice, WhatsApp, SMS, and Email from a unified platform
6. **Smart Escalation**: Automatic human handoff when needed
7. **Automated Follow-ups**: Scheduled reminders and nurture sequences
8. **Scalable Infrastructure**: Containerized microservices with horizontal scaling

The system is designed to handle thousands of concurrent calls while maintaining sub-second response times for a natural conversation experience.
