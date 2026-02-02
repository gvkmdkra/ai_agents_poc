# Calling Agent

A voice AI agent that handles phone calls using Ultravox and Twilio integration.

## Features

- **Outbound Calls**: Initiate AI-powered outbound calls to any phone number
- **Inbound Calls**: Handle incoming calls with voice AI
- **Real-time Transcription**: Get live transcripts of calls
- **Call Summaries**: Automatic summarization of completed calls using OpenAI
- **Webhook Integration**: Receive status updates and events from Twilio and Ultravox

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│    Twilio       │◄────┤  Calling Agent  │────►│    Ultravox     │
│  (Telephony)    │     │    (FastAPI)    │     │   (Voice AI)    │
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 │
                        ┌────────▼────────┐
                        │                 │
                        │     OpenAI      │
                        │  (Summaries)    │
                        │                 │
                        └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Twilio account with a phone number
- Ultravox API key
- OpenAI API key

### Installation

1. Clone the repository:
   ```bash
   cd calling_agent
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

### Running the Server

```bash
# Using the script
python scripts/run_server.py

# Or directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app
```

## API Endpoints

### Health & Status

- `GET /health` - Health check
- `GET /ready` - Readiness check with service status
- `GET /info` - Service information
- `GET /stats` - Call statistics

### Call Management

- `POST /api/v1/calls/initiate` - Initiate an outbound call
- `GET /api/v1/calls/{call_id}` - Get call details
- `POST /api/v1/calls/{call_id}/end` - End an active call
- `GET /api/v1/calls` - List call history
- `GET /api/v1/calls/active/list` - List active calls
- `GET /api/v1/calls/{call_id}/transcript` - Get call transcript
- `GET /api/v1/calls/{call_id}/summary` - Get call summary

### Webhooks

- `POST /api/v1/webhooks/twilio/voice` - Handle incoming calls
- `POST /api/v1/webhooks/twilio/connect/{call_id}` - Connect call to Ultravox
- `POST /api/v1/webhooks/twilio/status/{call_id}` - Call status updates
- `POST /api/v1/webhooks/ultravox/events` - Ultravox events

## Example Usage

### Initiate a Call

```bash
curl -X POST "http://localhost:8000/api/v1/calls/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+14155551234",
    "system_prompt": "You are a helpful assistant.",
    "greeting_message": "Hello! How can I help you today?"
  }'
```

### Check Call Status

```bash
curl "http://localhost:8000/api/v1/calls/{call_id}"
```

### End a Call

```bash
curl -X POST "http://localhost:8000/api/v1/calls/{call_id}/end"
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ULTRAVOX_API_KEY` | Ultravox API key | Yes |
| `ULTRAVOX_VOICE_ID` | Ultravox voice ID | Yes |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | Yes |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Yes |
| `TWILIO_PHONE_NUMBER` | Twilio phone number | Yes |
| `API_BASE_URL` | Base URL for webhooks | Yes |
| `SERVER_HOST` | Server host | No (default: 0.0.0.0) |
| `SERVER_PORT` | Server port | No (default: 8000) |

### Webhook Configuration

For local development, use ngrok to expose your server:

```bash
ngrok http 8000
```

Then update `API_BASE_URL` in your `.env` to the ngrok URL.

## Project Structure

```
calling_agent/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── calls.py      # Call management endpoints
│   │   │   ├── webhooks.py   # Webhook handlers
│   │   │   └── health.py     # Health check endpoints
│   │   └── middleware/
│   ├── core/
│   │   ├── config.py         # Configuration management
│   │   └── logging.py        # Logging setup
│   ├── models/
│   │   └── call.py           # Data models
│   ├── services/
│   │   ├── voice/
│   │   │   └── ultravox_service.py
│   │   ├── telephony/
│   │   │   └── twilio_service.py
│   │   ├── llm/
│   │   │   └── openai_service.py
│   │   └── call_manager.py   # Call orchestration
│   └── main.py               # Application entry point
├── tests/
├── scripts/
├── requirements.txt
└── README.md
```

## License

MIT
# Deployment trigger - Sun, Feb  1, 2026 10:45:13 PM
