"""
Tests for service modules
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime


class TestUltravoxService:
    """Tests for Ultravox service"""

    @pytest.mark.asyncio
    @patch("app.services.voice.ultravox_service.httpx.AsyncClient")
    async def test_create_call_session_success(self, mock_client):
        """Test successful call session creation"""
        from app.services.voice.ultravox_service import UltravoxService

        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "callId": "test-call-id",
            "joinUrl": "wss://api.ultravox.ai/ws/test"
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_client_instance

        with patch("app.services.voice.ultravox_service.settings") as mock_settings:
            mock_settings.ultravox_api_key = "test-key"
            mock_settings.ultravox_api_endpoint = "https://api.ultravox.ai/api/calls"
            mock_settings.ultravox_voice_id = "test-voice"
            mock_settings.ultravox_model_name = "fixie-ai/ultravox"
            mock_settings.ultravox_default_voice = "Mark"
            mock_settings.ultravox_temperature = 0.2
            mock_settings.ultravox_http_timeout = 30.0

            service = UltravoxService()
            result = await service.create_call_session(
                system_prompt="Test prompt",
                greeting_message="Hello"
            )

            assert result["success"] is True
            assert result["call_id"] == "test-call-id"
            assert "join_url" in result

    def test_get_default_system_prompt(self):
        """Test default system prompt generation"""
        from app.services.voice.ultravox_service import UltravoxService

        with patch("app.services.voice.ultravox_service.settings") as mock_settings:
            mock_settings.ultravox_api_key = "test-key"
            mock_settings.ultravox_api_endpoint = "https://api.ultravox.ai/api/calls"
            mock_settings.ultravox_voice_id = "test-voice"
            mock_settings.ultravox_model_name = "fixie-ai/ultravox"
            mock_settings.ultravox_default_voice = "Mark"
            mock_settings.ultravox_temperature = 0.2
            mock_settings.ultravox_http_timeout = 30.0

            service = UltravoxService()
            prompt = service.get_default_system_prompt("TestAgent")

            assert "TestAgent" in prompt
            assert "assistant" in prompt.lower()


class TestTwilioService:
    """Tests for Twilio service"""

    def test_generate_connect_twiml(self):
        """Test TwiML generation for Ultravox connection"""
        from app.services.telephony.twilio_service import TwilioService

        with patch("app.services.telephony.twilio_service.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test-sid"
            mock_settings.twilio_auth_token = "test-token"
            mock_settings.twilio_phone_number = "+15551234567"
            mock_settings.api_base_url = "http://localhost:8000"

            with patch("app.services.telephony.twilio_service.Client"):
                service = TwilioService()
                twiml = service.generate_connect_twiml(
                    "wss://api.ultravox.ai/ws/test"
                )

                assert "<Response>" in twiml
                assert "<Connect>" in twiml
                assert "<Stream" in twiml

    def test_generate_hangup_twiml(self):
        """Test TwiML generation for hangup"""
        from app.services.telephony.twilio_service import TwilioService

        with patch("app.services.telephony.twilio_service.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test-sid"
            mock_settings.twilio_auth_token = "test-token"
            mock_settings.twilio_phone_number = "+15551234567"
            mock_settings.api_base_url = "http://localhost:8000"

            with patch("app.services.telephony.twilio_service.Client"):
                service = TwilioService()
                twiml = service.generate_hangup_twiml("Goodbye")

                assert "<Response>" in twiml
                assert "<Hangup" in twiml
                assert "Goodbye" in twiml

    def test_map_twilio_status(self):
        """Test Twilio status mapping"""
        from app.services.telephony.twilio_service import TwilioService
        from app.models.call import CallStatus

        with patch("app.services.telephony.twilio_service.settings") as mock_settings:
            mock_settings.twilio_account_sid = "test-sid"
            mock_settings.twilio_auth_token = "test-token"
            mock_settings.twilio_phone_number = "+15551234567"
            mock_settings.api_base_url = "http://localhost:8000"

            with patch("app.services.telephony.twilio_service.Client"):
                # Test status mappings
                assert TwilioService.map_twilio_status("queued") == CallStatus.PENDING
                assert TwilioService.map_twilio_status("ringing") == CallStatus.RINGING
                assert TwilioService.map_twilio_status("in-progress") == CallStatus.IN_PROGRESS
                assert TwilioService.map_twilio_status("completed") == CallStatus.COMPLETED
                assert TwilioService.map_twilio_status("failed") == CallStatus.FAILED


class TestOpenAIService:
    """Tests for OpenAI service"""

    @pytest.mark.asyncio
    @patch("app.services.llm.openai_service.AsyncOpenAI")
    async def test_chat_completion(self, mock_openai):
        """Test chat completion"""
        from app.services.llm.openai_service import OpenAIService

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"
        mock_choice.message.role = "assistant"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        with patch("app.services.llm.openai_service.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.openai_embedding_model = "text-embedding-3-small"

            service = OpenAIService()
            result = await service.chat_completion(
                messages=[{"role": "user", "content": "Hello"}]
            )

            assert result["success"] is True
            assert result["content"] == "Test response"
            assert "usage" in result


class TestCallManager:
    """Tests for Call Manager"""

    @pytest.mark.asyncio
    async def test_get_call_status_not_found(self):
        """Test getting status for non-existent call"""
        from app.services.call_manager import CallManager

        with patch("app.services.call_manager.settings") as mock_settings:
            mock_settings.call_records_file_path = "test_records.json"
            mock_settings.twilio_phone_number = "+15551234567"

            with patch("app.services.call_manager.UltravoxService"):
                with patch("app.services.call_manager.TwilioService"):
                    with patch("app.services.call_manager.OpenAIService"):
                        manager = CallManager()
                        result = await manager.get_call_status("nonexistent-id")
                        assert result is None

    @pytest.mark.asyncio
    async def test_add_transcript_entry(self):
        """Test adding transcript entries"""
        from app.services.call_manager import CallManager
        from app.models.call import CallRecord, CallStatus

        with patch("app.services.call_manager.settings") as mock_settings:
            mock_settings.call_records_file_path = "test_records.json"
            mock_settings.twilio_phone_number = "+15551234567"

            with patch("app.services.call_manager.UltravoxService"):
                with patch("app.services.call_manager.TwilioService"):
                    with patch("app.services.call_manager.OpenAIService"):
                        manager = CallManager()

                        # Add a test call
                        test_call = CallRecord(
                            call_id="test-call",
                            status=CallStatus.IN_PROGRESS,
                            phone_number="+14155551234",
                            from_number="+15551234567"
                        )
                        manager.active_calls["test-call"] = test_call

                        # Add transcript entry
                        await manager.add_transcript_entry(
                            call_id="test-call",
                            speaker="user",
                            text="Hello there"
                        )

                        assert len(test_call.transcript) == 1
                        assert test_call.transcript[0].text == "Hello there"
                        assert test_call.transcript[0].speaker == "user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
