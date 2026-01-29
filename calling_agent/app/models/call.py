"""
Data models for call management
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CallStatus(str, Enum):
    """Status of a call"""
    PENDING = "pending"
    INITIATING = "initiating"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallDirection(str, Enum):
    """Direction of the call"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallRequest(BaseModel):
    """Request model for initiating a call"""
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone_number": "+14155551234",
                "system_prompt": "You are a helpful assistant.",
                "greeting_message": "Hello! How can I help you today?",
                "metadata": {"customer_id": "12345"},
                "max_duration_seconds": 600
            }
        }
    }

    phone_number: str = Field(..., description="Phone number to call (E.164 format)")
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt for the AI agent"
    )
    greeting_message: Optional[str] = Field(
        default=None,
        description="Initial greeting message"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata for the call"
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="Override voice ID for Ultravox"
    )
    max_duration_seconds: Optional[int] = Field(
        default=600,
        description="Maximum call duration in seconds"
    )


class CallResponse(BaseModel):
    """Response model after initiating a call"""
    call_id: str = Field(..., description="Unique identifier for the call")
    status: CallStatus = Field(..., description="Current status of the call")
    phone_number: str = Field(..., description="Phone number being called")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ultravox_call_id: Optional[str] = Field(None, description="Ultravox session ID")
    twilio_call_sid: Optional[str] = Field(None, description="Twilio call SID")
    message: Optional[str] = Field(None, description="Additional status message")


class CallTranscript(BaseModel):
    """Transcript entry for a call"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    speaker: str = Field(..., description="Speaker identifier (agent/user)")
    text: str = Field(..., description="Transcribed text")
    confidence: Optional[float] = Field(None, description="Transcription confidence score")


class CallSummary(BaseModel):
    """Summary of a completed call"""
    call_id: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = Field(None, description="Overall call sentiment")
    action_items: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CallRecord(BaseModel):
    """Complete record of a call"""
    call_id: str = Field(..., description="Unique call identifier")
    status: CallStatus = Field(default=CallStatus.PENDING)
    direction: CallDirection = Field(default=CallDirection.OUTBOUND)
    phone_number: str
    from_number: str
    ultravox_call_id: Optional[str] = None
    twilio_call_sid: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    # Content
    system_prompt: Optional[str] = None
    greeting_message: Optional[str] = None
    transcript: List[CallTranscript] = Field(default_factory=list)
    summary: Optional[CallSummary] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class WebhookEvent(BaseModel):
    """Webhook event from Twilio or Ultravox"""
    event_type: str
    call_sid: Optional[str] = None
    call_id: Optional[str] = None
    status: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)


class InboundCallRequest(BaseModel):
    """Model for handling inbound calls from Twilio"""
    CallSid: str
    AccountSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str
    ApiVersion: Optional[str] = None
    ForwardedFrom: Optional[str] = None
    CallerName: Optional[str] = None
    FromCity: Optional[str] = None
    FromState: Optional[str] = None
    FromZip: Optional[str] = None
    FromCountry: Optional[str] = None
    ToCity: Optional[str] = None
    ToState: Optional[str] = None
    ToZip: Optional[str] = None
    ToCountry: Optional[str] = None
