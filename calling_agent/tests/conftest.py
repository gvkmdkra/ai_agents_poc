"""
Pytest configuration and fixtures
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set test environment variables before importing app modules
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ULTRAVOX_API_KEY", "test-ultravox-key")
os.environ.setdefault("ULTRAVOX_VOICE_ID", "test-voice-id")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test-account-sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15551234567")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")

from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings():
    """Fixture for mocked settings"""
    with patch("app.core.config.settings") as mock:
        mock.openai_api_key = "test-openai-key"
        mock.openai_model = "gpt-4o-mini"
        mock.openai_embedding_model = "text-embedding-3-small"
        mock.ultravox_api_key = "test-ultravox-key"
        mock.ultravox_api_endpoint = "https://api.ultravox.ai/api/calls"
        mock.ultravox_voice_id = "test-voice-id"
        mock.ultravox_model_name = "fixie-ai/ultravox"
        mock.ultravox_default_voice = "Mark"
        mock.ultravox_temperature = 0.2
        mock.ultravox_http_timeout = 30.0
        mock.twilio_account_sid = "test-account-sid"
        mock.twilio_auth_token = "test-auth-token"
        mock.twilio_phone_number = "+15551234567"
        mock.api_base_url = "http://localhost:8000"
        mock.environment = "test"
        mock.debug = False
        mock.cors_origins = ["http://localhost:3000"]
        mock.call_records_file_path = "test_call_records.json"
        yield mock


@pytest.fixture
def mock_ultravox_service():
    """Fixture for mocked Ultravox service"""
    with patch("app.services.voice.ultravox_service.UltravoxService") as mock:
        instance = mock.return_value
        instance.create_call_session = AsyncMock(return_value={
            "success": True,
            "call_id": "ultravox-test-call-id",
            "join_url": "wss://api.ultravox.ai/ws/test"
        })
        instance.end_call = AsyncMock(return_value={"success": True})
        instance.get_call_status = AsyncMock(return_value={"success": True, "data": {}})
        instance.get_default_system_prompt = MagicMock(return_value="Test system prompt")
        yield instance


@pytest.fixture
def mock_twilio_service():
    """Fixture for mocked Twilio service"""
    with patch("app.services.telephony.twilio_service.TwilioService") as mock:
        instance = mock.return_value
        instance.initiate_call = AsyncMock(return_value={
            "success": True,
            "call_sid": "twilio-test-call-sid"
        })
        instance.end_call = AsyncMock(return_value={"success": True})
        instance.get_call = AsyncMock(return_value={"success": True, "status": "in-progress"})
        instance.generate_connect_twiml = MagicMock(return_value="<Response><Connect /></Response>")
        instance.generate_hangup_twiml = MagicMock(return_value="<Response><Hangup /></Response>")
        instance.map_twilio_status = MagicMock(side_effect=lambda x: x)
        yield instance


@pytest.fixture
def mock_openai_service():
    """Fixture for mocked OpenAI service"""
    with patch("app.services.llm.openai_service.OpenAIService") as mock:
        instance = mock.return_value
        instance.chat_completion = AsyncMock(return_value={
            "success": True,
            "content": "Test response"
        })
        instance.generate_call_summary = AsyncMock(return_value={
            "success": True,
            "content": '{"summary": "Test summary", "key_points": [], "action_items": []}'
        })
        yield instance


@pytest.fixture
def test_client(mock_settings):
    """Fixture for test client"""
    from app.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_call_request():
    """Sample call request data"""
    return {
        "phone_number": "+14155551234",
        "system_prompt": "You are a helpful assistant.",
        "greeting_message": "Hello! How can I help you?",
        "metadata": {"customer_id": "12345"}
    }
