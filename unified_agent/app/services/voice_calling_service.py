"""
Voice Calling Service
Handles Ultravox voice AI and Twilio telephony integration
"""

import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import CallError, ExternalServiceError
from app.db.models import Tenant, Call

logger = get_logger(__name__)


class UltravoxService:
    """
    Service for interacting with Ultravox Voice AI API
    """

    def __init__(self):
        self.api_key = settings.ultravox_api_key
        self.api_url = settings.ultravox_api_url
        self.default_voice = settings.ultravox_voice
        self.model = settings.ultravox_model

    async def create_call(
        self,
        system_prompt: str,
        voice: Optional[str] = None,
        first_speaker: str = "AGENT",
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        medium: Optional[Dict[str, Any]] = None,
        initial_output_medium: str = "voice",
        max_duration: int = 3600,
        recording_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Create an Ultravox call

        Args:
            system_prompt: AI system prompt
            voice: Voice to use
            first_speaker: Who speaks first (AGENT or USER)
            temperature: Response temperature
            tools: Tools available to the AI
            medium: Call medium configuration (twilio, webRTC)
            initial_output_medium: Initial output medium
            max_duration: Maximum call duration in seconds
            recording_enabled: Enable call recording

        Returns:
            Call creation response with join_url
        """
        try:
            payload = {
                "systemPrompt": system_prompt,
                "model": self.model,
                "voice": voice or self.default_voice,
                "temperature": temperature,
                "firstSpeaker": first_speaker,
                "maxDuration": f"{max_duration}s",
                "recordingEnabled": recording_enabled,
                "initialOutputMedium": initial_output_medium
            }

            if tools:
                payload["selectedTools"] = tools

            if medium:
                payload["medium"] = medium

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/calls",
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=30.0
                )

                if response.status_code != 201:
                    logger.error(f"Ultravox API error: {response.status_code} - {response.text}")
                    raise ExternalServiceError("ultravox", f"API error: {response.status_code}")

                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Ultravox request failed: {e}")
            raise ExternalServiceError("ultravox", f"Request failed: {e}")

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get call status from Ultravox"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/api/calls/{call_id}",
                    headers={"X-API-Key": self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    raise ExternalServiceError("ultravox", f"Status check failed: {response.status_code}")

                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Ultravox status check failed: {e}")
            raise ExternalServiceError("ultravox", f"Status check failed: {e}")

    async def end_call(self, call_id: str) -> bool:
        """End an active Ultravox call"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.api_url}/api/calls/{call_id}",
                    headers={"X-API-Key": self.api_key},
                    timeout=10.0
                )

                return response.status_code in [200, 204]

        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False


class TwilioService:
    """
    Service for Twilio telephony integration
    """

    def __init__(self):
        from twilio.rest import Client
        from twilio.twiml.voice_response import VoiceResponse

        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.phone_number = settings.twilio_phone_number

        self._client = Client(self.account_sid, self.auth_token)

    def create_outbound_call(
        self,
        to_number: str,
        twiml_url: str,
        status_callback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an outbound phone call via Twilio

        Args:
            to_number: Destination phone number
            twiml_url: URL for TwiML instructions
            status_callback: URL for status callbacks

        Returns:
            Twilio call information
        """
        try:
            call = self._client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=twiml_url,
                status_callback=status_callback,
                status_callback_event=["initiated", "ringing", "answered", "completed"]
            )

            return {
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from_": call.from_
            }

        except Exception as e:
            logger.error(f"Twilio call creation failed: {e}")
            raise ExternalServiceError("twilio", f"Call creation failed: {e}")

    def generate_connect_twiml(
        self,
        ultravox_join_url: str
    ) -> str:
        """
        Generate TwiML to connect call to Ultravox

        Args:
            ultravox_join_url: Ultravox WebSocket URL

        Returns:
            TwiML XML string
        """
        from twilio.twiml.voice_response import VoiceResponse, Connect

        response = VoiceResponse()
        connect = Connect()
        connect.stream(url=ultravox_join_url)
        response.append(connect)

        return str(response)

    def get_call_info(self, call_sid: str) -> Dict[str, Any]:
        """Get call information from Twilio"""
        try:
            call = self._client.calls(call_sid).fetch()
            return {
                "call_sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None
            }
        except Exception as e:
            logger.error(f"Failed to get call info: {e}")
            return {}


class VoiceCallingService:
    """
    Unified voice calling service combining Ultravox and Twilio
    """

    def __init__(self, tenant: Tenant):
        """
        Initialize voice calling service

        Args:
            tenant: Tenant configuration
        """
        self.tenant = tenant
        self._ultravox = UltravoxService()
        self._twilio = TwilioService()
        self._openai = OpenAI(api_key=settings.openai_api_key)

    def _build_system_prompt(
        self,
        client_name: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        include_database_tools: bool = False
    ) -> str:
        """Build system prompt for voice AI"""

        base_prompt = custom_prompt or self.tenant.system_prompt or f"""You are a helpful AI assistant for {self.tenant.name}.

Your role is to assist callers with their questions and needs. Be professional, friendly, and helpful.

Guidelines:
- Listen carefully to the caller's questions
- Provide clear, concise answers
- If you don't know something, say so honestly
- Offer to help with related questions"""

        if client_name:
            base_prompt += f"\n\nYou are speaking with {client_name}."

        if include_database_tools:
            base_prompt += """

You have access to a database query tool. When users ask about specific data, counts, or business information, use the query_database tool to get accurate information.

Tool usage guidelines:
- Use query_database for questions about data, statistics, client info, or metrics
- Wait for the tool response before speaking
- If the query fails, apologize and offer to help differently"""

        return base_prompt

    def _get_call_tools(
        self,
        websocket_url: str,
        include_database: bool = True
    ) -> List[Dict[str, Any]]:
        """Get tools for the voice call"""

        tools = []

        if include_database:
            tools.append({
                "temporaryTool": {
                    "modelToolName": "query_database",
                    "description": "Query the database for business information, statistics, client data, or metrics",
                    "dynamicParameters": [
                        {
                            "name": "query",
                            "location": "PARAMETER_LOCATION_BODY",
                            "schema": {
                                "type": "string",
                                "description": "The natural language query to execute"
                            },
                            "required": True
                        }
                    ],
                    "http": {
                        "baseUrlPattern": websocket_url,
                        "httpMethod": "POST"
                    },
                    "timeout": "60s"
                }
            })

        # End call tool
        tools.append({
            "temporaryTool": {
                "modelToolName": "end_call",
                "description": "End the current call when the conversation is complete",
                "dynamicParameters": [],
                "client": {}
            }
        })

        return tools

    async def create_browser_call(
        self,
        client_name: Optional[str] = None,
        userid: Optional[int] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a browser-based WebRTC voice call

        Args:
            client_name: Name of the caller
            userid: User ID for data filtering
            custom_prompt: Custom system prompt

        Returns:
            Call information with join URL
        """
        try:
            # Determine if database tools should be available
            include_database = bool(userid) and settings.enable_text_to_sql

            # Build system prompt
            system_prompt = self._build_system_prompt(
                client_name=client_name,
                custom_prompt=custom_prompt,
                include_database_tools=include_database
            )

            # Build WebSocket URL for tool handling
            websocket_base = settings.api_base_url.replace("http", "ws")
            websocket_url = f"{websocket_base}/ws/ultravox?tenant_id={self.tenant.id}"
            if userid:
                websocket_url += f"&userid={userid}"

            # Get tools
            tools = self._get_call_tools(
                websocket_url=websocket_url,
                include_database=include_database
            )

            # Create Ultravox call
            result = await self._ultravox.create_call(
                system_prompt=system_prompt,
                voice=self.tenant.voice or settings.ultravox_voice,
                first_speaker="AGENT",
                tools=tools,
                initial_output_medium="voice"
            )

            return {
                "success": True,
                "call_id": result.get("callId"),
                "join_url": result.get("joinUrl"),
                "database_enabled": include_database
            }

        except Exception as e:
            logger.error(f"Browser call creation failed: {e}")
            raise CallError(f"Failed to create call: {e}")

    async def create_phone_call(
        self,
        phone_number: str,
        client_name: Optional[str] = None,
        userid: Optional[int] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an outbound phone call via Twilio

        Args:
            phone_number: Destination phone number
            client_name: Name of the person being called
            userid: User ID for data filtering
            custom_prompt: Custom system prompt

        Returns:
            Call information
        """
        try:
            include_database = bool(userid) and settings.enable_text_to_sql

            # Build system prompt
            system_prompt = self._build_system_prompt(
                client_name=client_name,
                custom_prompt=custom_prompt,
                include_database_tools=include_database
            )

            # Build WebSocket URL
            websocket_base = settings.api_base_url.replace("http", "ws")
            websocket_url = f"{websocket_base}/ws/ultravox?tenant_id={self.tenant.id}"
            if userid:
                websocket_url += f"&userid={userid}"

            tools = self._get_call_tools(
                websocket_url=websocket_url,
                include_database=include_database
            )

            # Create Ultravox call with Twilio medium
            ultravox_result = await self._ultravox.create_call(
                system_prompt=system_prompt,
                voice=self.tenant.voice or settings.ultravox_voice,
                first_speaker="AGENT",
                tools=tools,
                medium={"twilio": {}},
                initial_output_medium="voice"
            )

            # Create Twilio call
            twiml_url = f"{settings.api_base_url}/api/v1/webhooks/twiml?call_id={ultravox_result['callId']}"
            twilio_result = self._twilio.create_outbound_call(
                to_number=phone_number,
                twiml_url=twiml_url,
                status_callback=f"{settings.api_base_url}/api/v1/webhooks/twilio/status"
            )

            return {
                "success": True,
                "ultravox_call_id": ultravox_result.get("callId"),
                "twilio_call_sid": twilio_result.get("call_sid"),
                "phone_number": phone_number,
                "database_enabled": include_database
            }

        except Exception as e:
            logger.error(f"Phone call creation failed: {e}")
            raise CallError(f"Failed to create call: {e}")

    async def generate_call_summary(
        self,
        transcript: str
    ) -> Dict[str, Any]:
        """
        Generate a summary of the call

        Args:
            transcript: Call transcript

        Returns:
            Summary with key points
        """
        try:
            prompt = f"""Analyze this call transcript and provide a structured summary:

Transcript:
{transcript}

Provide:
1. Main purpose of the call (1-2 sentences)
2. Key topics discussed (bullet points)
3. Any issues or concerns raised
4. Action items or follow-ups needed
5. Overall sentiment (positive, neutral, negative)

Keep the summary concise and professional."""

            response = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            return {
                "summary": response.choices[0].message.content,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return {"summary": "Unable to generate summary", "error": str(e)}
