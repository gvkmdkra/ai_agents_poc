"""
Ultravox Integration Client

Real-time voice AI for natural conversations with:
- Sub-200ms latency
- Streaming ASR (Speech-to-Text)
- Neural TTS (Text-to-Speech)
- Turn-taking detection
- Tool calling support
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

import aiohttp

logger = logging.getLogger(__name__)


class UltravoxEventType(str, Enum):
    """Ultravox WebSocket event types"""

    # Session events
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_ENDED = "session.ended"

    # Audio events
    AUDIO_OUTPUT = "audio.output"
    AUDIO_INPUT_STARTED = "audio.input.started"
    AUDIO_INPUT_ENDED = "audio.input.ended"

    # Transcript events
    TRANSCRIPT_PARTIAL = "transcript.partial"
    TRANSCRIPT_FINAL = "transcript.final"

    # Turn events
    TURN_STARTED = "turn.started"
    TURN_ENDED = "turn.ended"

    # Tool events
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"

    # Error events
    ERROR = "error"


@dataclass
class VoiceSettings:
    """Voice configuration for Ultravox"""

    provider: str = "elevenlabs"  # elevenlabs, playht, azure, deepgram
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs voice ID
    language: str = "en-US"
    speaking_rate: float = 1.0
    pitch: float = 1.0
    stability: float = 0.5  # ElevenLabs specific
    similarity_boost: float = 0.75  # ElevenLabs specific


@dataclass
class ASRSettings:
    """ASR (Speech-to-Text) configuration"""

    provider: str = "deepgram"  # deepgram, whisper, azure
    model: str = "nova-2"
    language: str = "en-US"
    punctuate: bool = True
    profanity_filter: bool = False
    smart_format: bool = True


@dataclass
class TurnDetectionSettings:
    """Turn-taking detection configuration"""

    type: str = "server_vad"  # server_vad, semantic
    threshold: float = 0.5
    prefix_padding_ms: int = 300
    silence_duration_ms: int = 500
    max_duration_ms: int = 30000


@dataclass
class ToolDefinition:
    """Tool definition for function calling"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Optional[Callable] = None


@dataclass
class UltravoxConfig:
    """Ultravox client configuration"""

    api_key: str
    api_url: str = "wss://api.ultravox.ai/v1/realtime"
    http_url: str = "https://api.ultravox.ai/v1"
    model: str = "fixie-ai/ultravox-v0.4"
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    asr: ASRSettings = field(default_factory=ASRSettings)
    turn_detection: TurnDetectionSettings = field(default_factory=TurnDetectionSettings)
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation"""

    id: str
    role: str  # user, assistant
    text: str
    timestamp: datetime
    audio_duration_ms: Optional[int] = None
    confidence: Optional[float] = None
    sentiment: Optional[float] = None


class UltravoxSession:
    """
    Manages a single Ultravox voice AI session.

    Handles real-time bidirectional audio streaming and conversation state.
    """

    def __init__(
        self,
        config: UltravoxConfig,
        session_id: str,
        system_prompt: str,
        tools: Optional[list[ToolDefinition]] = None,
    ):
        self.config = config
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.tools = tools or []

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._conversation_history: list[ConversationTurn] = []

        # Event handlers
        self._event_handlers: dict[UltravoxEventType, list[Callable]] = {}

        # Audio buffers
        self._input_audio_buffer: bytearray = bytearray()
        self._output_audio_buffer: bytearray = bytearray()

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Ultravox.

        Returns:
            True if connection successful
        """
        try:
            self._http_session = aiohttp.ClientSession()

            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "X-Session-ID": self.session_id,
            }

            self._ws = await self._http_session.ws_connect(
                self.config.api_url,
                headers=headers,
                heartbeat=30,
            )

            self._running = True

            # Send session configuration
            await self._send_session_config()

            logger.info(f"Ultravox session connected: {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Ultravox: {e}")
            return False

    async def _send_session_config(self):
        """Send initial session configuration"""

        config_message = {
            "type": "session.create",
            "session_id": self.session_id,
            "model": self.config.model,
            "system_prompt": self.system_prompt,
            "voice": {
                "provider": self.config.voice.provider,
                "voice_id": self.config.voice.voice_id,
                "language": self.config.voice.language,
                "speaking_rate": self.config.voice.speaking_rate,
                "settings": {
                    "stability": self.config.voice.stability,
                    "similarity_boost": self.config.voice.similarity_boost,
                },
            },
            "asr": {
                "provider": self.config.asr.provider,
                "model": self.config.asr.model,
                "language": self.config.asr.language,
                "punctuate": self.config.asr.punctuate,
                "smart_format": self.config.asr.smart_format,
            },
            "turn_detection": {
                "type": self.config.turn_detection.type,
                "threshold": self.config.turn_detection.threshold,
                "prefix_padding_ms": self.config.turn_detection.prefix_padding_ms,
                "silence_duration_ms": self.config.turn_detection.silence_duration_ms,
            },
            "generation": {
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            },
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
                for tool in self.tools
            ],
        }

        await self._send_message(config_message)

    async def _send_message(self, message: dict):
        """Send a message to Ultravox"""
        if self._ws:
            await self._ws.send_json(message)

    async def disconnect(self):
        """Close the Ultravox session"""
        self._running = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._http_session:
            await self._http_session.close()
            self._http_session = None

        logger.info(f"Ultravox session disconnected: {self.session_id}")

    def on(self, event_type: UltravoxEventType, handler: Callable):
        """
        Register an event handler.

        Args:
            event_type: Type of event to handle
            handler: Async callback function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: UltravoxEventType, data: dict):
        """Emit an event to registered handlers"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def send_audio(self, audio_data: bytes, encoding: str = "pcm_s16le", sample_rate: int = 16000):
        """
        Send audio data to Ultravox for processing.

        Args:
            audio_data: Raw audio bytes
            encoding: Audio encoding (pcm_s16le, mulaw, etc.)
            sample_rate: Sample rate in Hz
        """
        if not self._ws:
            return

        message = {
            "type": "audio.input",
            "audio": base64.b64encode(audio_data).decode("utf-8"),
            "encoding": encoding,
            "sample_rate": sample_rate,
        }

        await self._send_message(message)

    async def send_text(self, text: str):
        """
        Send text input (for testing or text-based interaction).

        Args:
            text: Text to process
        """
        if not self._ws:
            return

        message = {
            "type": "text.input",
            "text": text,
        }

        await self._send_message(message)

    async def interrupt(self, reason: str = "user_interrupt"):
        """
        Interrupt the current AI response.

        Args:
            reason: Reason for interruption
        """
        if not self._ws:
            return

        message = {
            "type": "conversation.interrupt",
            "reason": reason,
        }

        await self._send_message(message)
        logger.debug(f"Interrupted conversation: {reason}")

    async def send_tool_result(self, tool_call_id: str, result: Any):
        """
        Send the result of a tool call back to Ultravox.

        Args:
            tool_call_id: ID of the tool call
            result: Result data
        """
        if not self._ws:
            return

        message = {
            "type": "tool.result",
            "tool_call_id": tool_call_id,
            "result": json.dumps(result) if not isinstance(result, str) else result,
        }

        await self._send_message(message)

    async def listen(self):
        """
        Main event loop for receiving Ultravox events.

        This should be run in a separate task.
        """
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(json.loads(msg.data))
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # Binary audio data
                    self._output_audio_buffer.extend(msg.data)
                    await self._emit_event(
                        UltravoxEventType.AUDIO_OUTPUT,
                        {"audio": msg.data},
                    )
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

        except Exception as e:
            logger.error(f"Listen loop error: {e}")
        finally:
            self._running = False

    async def _handle_message(self, message: dict):
        """Handle incoming Ultravox message"""
        msg_type = message.get("type", "")

        try:
            event_type = UltravoxEventType(msg_type)
        except ValueError:
            logger.warning(f"Unknown message type: {msg_type}")
            return

        # Process specific message types
        if event_type == UltravoxEventType.TRANSCRIPT_FINAL:
            turn = ConversationTurn(
                id=str(uuid4()),
                role=message.get("role", "unknown"),
                text=message.get("text", ""),
                timestamp=datetime.now(),
                confidence=message.get("confidence"),
            )
            self._conversation_history.append(turn)

        elif event_type == UltravoxEventType.TOOL_CALL:
            # Handle tool calls
            tool_name = message.get("name")
            tool_args = message.get("arguments", {})
            tool_call_id = message.get("tool_call_id")

            # Find and execute the tool handler
            for tool in self.tools:
                if tool.name == tool_name and tool.handler:
                    try:
                        result = await tool.handler(tool_args)
                        await self.send_tool_result(tool_call_id, result)
                    except Exception as e:
                        logger.error(f"Tool execution error: {e}")
                        await self.send_tool_result(
                            tool_call_id,
                            {"error": str(e)},
                        )
                    break

        elif event_type == UltravoxEventType.AUDIO_OUTPUT:
            # Audio is handled in binary messages
            audio_b64 = message.get("audio")
            if audio_b64:
                audio_data = base64.b64decode(audio_b64)
                self._output_audio_buffer.extend(audio_data)

        # Emit event to handlers
        await self._emit_event(event_type, message)

    def get_conversation_history(self) -> list[ConversationTurn]:
        """Get the full conversation history"""
        return self._conversation_history.copy()

    def get_transcript(self) -> str:
        """Get the conversation as a formatted transcript"""
        lines = []
        for turn in self._conversation_history:
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.text}")
        return "\n".join(lines)

    @property
    def is_connected(self) -> bool:
        """Check if session is connected"""
        return self._ws is not None and not self._ws.closed


class UltravoxClient:
    """
    High-level Ultravox client for managing voice AI sessions.

    Example usage:
        config = UltravoxConfig(api_key="your-api-key")
        client = UltravoxClient(config)

        session = await client.create_session(
            system_prompt="You are a helpful assistant...",
            tools=[...],
        )

        # Handle audio streaming
        session.on(UltravoxEventType.AUDIO_OUTPUT, handle_audio)
        session.on(UltravoxEventType.TRANSCRIPT_FINAL, handle_transcript)

        # Start listening for events
        asyncio.create_task(session.listen())

        # Send audio from Twilio media stream
        await session.send_audio(audio_data)
    """

    def __init__(self, config: UltravoxConfig):
        self.config = config
        self._sessions: dict[str, UltravoxSession] = {}

    async def create_session(
        self,
        system_prompt: str,
        tools: Optional[list[ToolDefinition]] = None,
        session_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
    ) -> UltravoxSession:
        """
        Create a new Ultravox session.

        Args:
            system_prompt: System prompt for the AI
            tools: Optional tool definitions
            session_id: Optional custom session ID
            voice_settings: Optional custom voice settings

        Returns:
            Connected UltravoxSession
        """
        session_id = session_id or str(uuid4())

        # Apply custom voice settings if provided
        config = self.config
        if voice_settings:
            config = UltravoxConfig(
                api_key=self.config.api_key,
                api_url=self.config.api_url,
                model=self.config.model,
                voice=voice_settings,
                asr=self.config.asr,
                turn_detection=self.config.turn_detection,
            )

        session = UltravoxSession(
            config=config,
            session_id=session_id,
            system_prompt=system_prompt,
            tools=tools,
        )

        success = await session.connect()
        if not success:
            raise ConnectionError("Failed to connect to Ultravox")

        self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[UltravoxSession]:
        """Get an existing session by ID"""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str):
        """Close and remove a session"""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.disconnect()

    async def close_all_sessions(self):
        """Close all active sessions"""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs"""
        return list(self._sessions.keys())
