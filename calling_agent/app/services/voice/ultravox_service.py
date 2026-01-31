"""
Ultravox Voice AI Service
Handles voice AI interactions using the Ultravox API
Includes retry logic for resilient API calls
"""

import httpx
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import UltravoxServiceError
from app.models.call import CallStatus

logger = get_logger(__name__)


class UltravoxService:
    """Service for interacting with Ultravox Voice AI API"""

    def __init__(self):
        self.api_key = settings.ultravox_api_key
        self.api_endpoint = settings.ultravox_api_endpoint
        self.voice_id = settings.ultravox_voice_id
        self.model_name = settings.ultravox_model_name
        self.default_voice = settings.ultravox_default_voice
        self.temperature = settings.ultravox_temperature
        self.timeout = settings.ultravox_http_timeout

        # Retry configuration
        self.max_retries = settings.api_max_retries
        self.retry_delay = settings.api_retry_delay

        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _debug_log(self, message: str, start_time: Optional[float] = None) -> float:
        """Enhanced debug logging with timestamps and elapsed time"""
        current_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if start_time:
            elapsed = current_time - start_time
            logger.debug(f"[{timestamp}] [{elapsed:.3f}s elapsed] {message}")
        else:
            logger.debug(f"[{timestamp}] {message}")
        return current_time

    async def create_call_session(
        self,
        system_prompt: str,
        greeting_message: Optional[str] = None,
        voice_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new Ultravox call session

        Args:
            system_prompt: System prompt for the AI agent
            greeting_message: Initial greeting message
            voice_id: Optional voice ID override
            tools: Optional list of tools for the agent
            metadata: Optional metadata

        Returns:
            Session data including join URL and session ID
        """
        logger.info("Creating Ultravox call session")

        payload = {
            "systemPrompt": system_prompt,
            "model": self.model_name,
            "voice": voice_id or self.voice_id or self.default_voice,
            "temperature": self.temperature,
            "medium": {
                "twilio": {}
            }
        }

        if greeting_message:
            payload["firstSpeaker"] = "FIRST_SPEAKER_AGENT"
            payload["firstSpeakerMessage"] = greeting_message

        if tools:
            payload["selectedTools"] = tools

        if metadata:
            # Truncate metadata if too long
            metadata_str = json.dumps(metadata)
            if len(metadata_str) > 2000:
                logger.warning("Metadata too long, truncating")
                metadata_str = metadata_str[:2000]
            payload["metadata"] = metadata_str

        start_time = self._debug_log(f"Starting Ultravox API call with retry support")
        last_exception = None
        current_delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                attempt_start = self._debug_log(f"Ultravox API attempt {attempt}/{self.max_retries}")

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.api_endpoint,
                        headers=self.headers,
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()

                    self._debug_log(f"Ultravox API attempt {attempt} successful", attempt_start)
                    logger.info(f"Ultravox session created: {result.get('callId', 'unknown')}")

                    return {
                        "success": True,
                        "call_id": result.get("callId"),
                        "join_url": result.get("joinUrl"),
                        "created_at": datetime.utcnow().isoformat(),
                        "raw_response": result
                    }

            except httpx.HTTPStatusError as e:
                last_exception = e
                self._debug_log(
                    f"Attempt {attempt}/{self.max_retries} - HTTP Error: {e.response.status_code}",
                    attempt_start
                )
                logger.warning(f"Ultravox API error (attempt {attempt}): {e.response.text}")

                if attempt < self.max_retries:
                    import asyncio
                    await asyncio.sleep(current_delay)
                    current_delay *= 2  # Exponential backoff

            except Exception as e:
                last_exception = e
                self._debug_log(f"Attempt {attempt}/{self.max_retries} - Error: {str(e)}", attempt_start)
                logger.warning(f"Ultravox request failed (attempt {attempt}): {str(e)}")

                if attempt < self.max_retries:
                    import asyncio
                    await asyncio.sleep(current_delay)
                    current_delay *= 2

        # All retries exhausted
        self._debug_log(f"All {self.max_retries} attempts failed", start_time)
        logger.error(f"Failed to create Ultravox session after {self.max_retries} attempts")

        if isinstance(last_exception, httpx.HTTPStatusError):
            return {
                "success": False,
                "error": f"API error: {last_exception.response.status_code}",
                "details": last_exception.response.text
            }
        return {
            "success": False,
            "error": str(last_exception) if last_exception else "Unknown error"
        }

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get the status of an Ultravox call

        Args:
            call_id: Ultravox call ID

        Returns:
            Call status information
        """
        logger.debug(f"Getting Ultravox call status: {call_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_endpoint}/{call_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return {
                    "success": True,
                    "data": response.json()
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get call status: {e.response.status_code}")
            return {
                "success": False,
                "error": f"API error: {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"Error getting call status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """
        End an active Ultravox call

        Args:
            call_id: Ultravox call ID

        Returns:
            Result of the end call operation
        """
        logger.info(f"Ending Ultravox call: {call_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    f"{self.api_endpoint}/{call_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return {
                    "success": True,
                    "message": "Call ended successfully"
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to end call: {e.response.status_code}")
            return {
                "success": False,
                "error": f"API error: {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"Error ending call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_call_transcript(self, call_id: str) -> Dict[str, Any]:
        """
        Get the transcript for a completed call

        Args:
            call_id: Ultravox call ID

        Returns:
            Call transcript data
        """
        logger.debug(f"Getting transcript for call: {call_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_endpoint}/{call_id}/transcript",
                    headers=self.headers
                )
                response.raise_for_status()
                return {
                    "success": True,
                    "transcript": response.json()
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "error": "Transcript not available"
                }
            logger.error(f"Failed to get transcript: {e.response.status_code}")
            return {
                "success": False,
                "error": f"API error: {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"Error getting transcript: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_default_system_prompt(self, agent_name: str = "Assistant") -> str:
        """
        Get a default system prompt for the voice agent

        Args:
            agent_name: Name of the agent

        Returns:
            Default system prompt
        """
        return f"""You are {agent_name}, a helpful and professional AI voice assistant.

Your responsibilities:
1. Answer questions clearly and concisely
2. Assist callers with their requests
3. Maintain a friendly and professional tone
4. If you don't know something, politely say so
5. Keep responses brief and suitable for voice conversation

Guidelines:
- Speak naturally as if having a phone conversation
- Avoid long pauses or overly complex explanations
- Confirm important information by repeating it back
- Ask clarifying questions when needed
- End conversations politely when the caller is done
"""

    def create_tool_definitions(
        self,
        tools: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Create tool definitions for Ultravox

        Args:
            tools: List of tool names to include

        Returns:
            List of tool definitions
        """
        available_tools = {
            "transfer_call": {
                "temporaryTool": {
                    "modelToolName": "transfer_call",
                    "description": "Transfer the call to a human agent",
                    "dynamicParameters": [
                        {
                            "name": "department",
                            "location": "PARAMETER_LOCATION_BODY",
                            "schema": {
                                "type": "string",
                                "description": "Department to transfer to"
                            },
                            "required": True
                        }
                    ]
                }
            },
            "schedule_callback": {
                "temporaryTool": {
                    "modelToolName": "schedule_callback",
                    "description": "Schedule a callback for the caller",
                    "dynamicParameters": [
                        {
                            "name": "datetime",
                            "location": "PARAMETER_LOCATION_BODY",
                            "schema": {
                                "type": "string",
                                "description": "Preferred callback date and time"
                            },
                            "required": True
                        },
                        {
                            "name": "reason",
                            "location": "PARAMETER_LOCATION_BODY",
                            "schema": {
                                "type": "string",
                                "description": "Reason for callback"
                            },
                            "required": False
                        }
                    ]
                }
            },
            "lookup_info": {
                "temporaryTool": {
                    "modelToolName": "lookup_info",
                    "description": "Look up information in the knowledge base",
                    "dynamicParameters": [
                        {
                            "name": "query",
                            "location": "PARAMETER_LOCATION_BODY",
                            "schema": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "required": True
                        }
                    ]
                }
            }
        }

        if tools is None:
            return []

        return [available_tools[t] for t in tools if t in available_tools]
