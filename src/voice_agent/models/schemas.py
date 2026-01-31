"""
Pydantic schemas for Voice Agent
"""

from datetime import datetime, time
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# =============================================================================
# ENUMS
# =============================================================================


class LeadTemperature(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    MEETING_SCHEDULED = "meeting_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"
    UNQUALIFIED = "unqualified"


class LeadSource(str, Enum):
    INBOUND_CALL = "inbound_call"
    OUTBOUND_CALL = "outbound_call"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    WEB = "web"
    EMAIL = "email"


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    FAILED = "failed"
    CANCELED = "canceled"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    PENDING_CONFIRMATION = "pending_confirmation"


class MeetingType(str, Enum):
    IN_PERSON = "in_person"
    PHONE = "phone"
    VIDEO = "video"


class NotificationChannel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"


class NotificationType(str, Enum):
    CONFIRMATION = "confirmation"
    REMINDER_24H = "reminder_24h"
    REMINDER_1H = "reminder_1h"
    FOLLOW_UP = "follow_up"
    MARKETING = "marketing"
    TRANSACTIONAL = "transactional"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BOUNCED = "bounced"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"


class PhoneType(str, Enum):
    VOICE = "voice"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    ALL = "all"


# =============================================================================
# TENANT SCHEMAS
# =============================================================================


class TenantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    industry: str = Field(..., min_length=1, max_length=50)
    timezone: str = Field(default="UTC")
    settings: dict[str, Any] = Field(default_factory=dict)


class TenantCreate(TenantBase):
    subscription_plan: str = Field(default="starter")


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    settings: Optional[dict[str, Any]] = None
    status: Optional[TenantStatus] = None


class Tenant(TenantBase):
    id: UUID
    status: TenantStatus = TenantStatus.ACTIVE
    subscription_plan: str
    monthly_minutes_limit: int
    minutes_used: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# PHONE NUMBER SCHEMAS
# =============================================================================


class PhoneNumberBase(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)
    phone_type: PhoneType
    display_name: Optional[str] = None
    purpose: Optional[str] = None
    language: str = Field(default="en-US")


class PhoneNumberCreate(PhoneNumberBase):
    tenant_id: UUID
    twilio_sid: Optional[str] = None
    twilio_phone_sid: Optional[str] = None


class PhoneNumber(PhoneNumberBase):
    id: UUID
    tenant_id: UUID
    twilio_sid: Optional[str] = None
    country_code: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# VOICE CONFIG SCHEMAS
# =============================================================================


class VoiceConfigBase(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=100)
    agent_role: Optional[str] = None
    greeting_script: str
    system_prompt: str
    voice_provider: str = Field(default="elevenlabs")
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    language: str = Field(default="en-US")
    accent: Optional[str] = None
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    max_conversation_turns: int = Field(default=50)
    escalation_keywords: list[str] = Field(
        default_factory=lambda: ["speak to human", "real person", "manager"]
    )


class VoiceConfigCreate(VoiceConfigBase):
    tenant_id: UUID
    industry_knowledge_base: Optional[str] = None
    faq_document: Optional[str] = None


class VoiceConfig(VoiceConfigBase):
    id: UUID
    tenant_id: UUID
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# BUSINESS HOURS SCHEMAS
# =============================================================================


class BusinessHoursBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)  # 0=Sunday, 6=Saturday
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = Field(default=False)
    after_hours_action: str = Field(default="voicemail")
    after_hours_message: Optional[str] = None


class BusinessHoursCreate(BusinessHoursBase):
    tenant_id: UUID


class BusinessHours(BusinessHoursBase):
    id: UUID
    tenant_id: UUID

    class Config:
        from_attributes = True


# =============================================================================
# LEAD SCHEMAS
# =============================================================================


class LeadBase(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=100)


class LeadCreate(LeadBase):
    tenant_id: UUID
    source: LeadSource
    source_phone_number: Optional[str] = None
    source_campaign: Optional[str] = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    lead_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[LeadStatus] = None
    assigned_to: Optional[UUID] = None
    next_follow_up_at: Optional[datetime] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None


class LeadQualificationData(BaseModel):
    budget_mentioned: bool = False
    budget_range: Optional[str] = None
    is_decision_maker: bool = False
    need_identified: Optional[str] = None
    timeline: Optional[str] = None  # immediate, 1-3 months, 6+ months
    pain_points: list[str] = Field(default_factory=list)
    competitors_mentioned: list[str] = Field(default_factory=list)
    questions_asked: list[str] = Field(default_factory=list)


class Lead(LeadBase):
    id: UUID
    tenant_id: UUID
    full_name: Optional[str] = None
    lead_score: float
    lead_temperature: Optional[LeadTemperature] = None
    qualification_data: dict[str, Any]
    source: LeadSource
    source_phone_number: Optional[str] = None
    odoo_lead_id: Optional[int] = None
    odoo_sync_status: str
    status: LeadStatus
    assigned_to: Optional[UUID] = None
    total_calls: int
    total_messages: int
    last_contact_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    tags: list[str]
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# CALL SCHEMAS
# =============================================================================


class TranscriptEntry(BaseModel):
    role: str  # "user" or "assistant"
    text: str
    timestamp: datetime
    confidence: Optional[float] = None
    sentiment: Optional[float] = None


class CallBase(BaseModel):
    direction: CallDirection
    from_number: str
    to_number: str


class CallCreate(CallBase):
    tenant_id: UUID
    lead_id: Optional[UUID] = None
    twilio_call_sid: Optional[str] = None
    voice_config_id: Optional[UUID] = None


class CallUpdate(BaseModel):
    status: Optional[CallStatus] = None
    duration_seconds: Optional[int] = None
    conversation_turns: Optional[int] = None
    ai_handled: Optional[bool] = None
    escalated_to_human: Optional[bool] = None
    escalation_reason: Optional[str] = None
    recording_url: Optional[str] = None
    transcript: Optional[list[dict]] = None
    transcript_summary: Optional[str] = None
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    intent_detected: Optional[list[str]] = None
    entities_extracted: Optional[dict[str, Any]] = None
    outcome: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None


class Call(CallBase):
    id: UUID
    tenant_id: UUID
    lead_id: Optional[UUID] = None
    twilio_call_sid: Optional[str] = None
    status: CallStatus
    duration_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    conversation_turns: int
    ai_handled: bool
    escalated_to_human: bool
    escalation_reason: Optional[str] = None
    recording_url: Optional[str] = None
    transcript: list[dict]
    transcript_summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    intent_detected: Optional[list[str]] = None
    outcome: Optional[str] = None
    follow_up_required: bool
    total_cost_usd: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# APPOINTMENT SCHEMAS
# =============================================================================


class AppointmentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    appointment_type: str = Field(default="consultation")
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    timezone: str
    meeting_type: MeetingType = MeetingType.PHONE
    location: Optional[str] = None
    meeting_link: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    tenant_id: UUID
    lead_id: UUID
    call_id: Optional[UUID] = None
    assigned_agent_id: Optional[UUID] = None
    agent_name: Optional[str] = None
    agent_email: Optional[EmailStr] = None


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    meeting_type: Optional[MeetingType] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: Optional[AppointmentStatus] = None
    assigned_agent_id: Optional[UUID] = None
    cancellation_reason: Optional[str] = None
    outcome: Optional[str] = None
    outcome_notes: Optional[str] = None


class Appointment(AppointmentBase):
    id: UUID
    tenant_id: UUID
    lead_id: Optional[UUID] = None
    call_id: Optional[UUID] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None
    assigned_agent_id: Optional[UUID] = None
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    status: AppointmentStatus
    confirmation_sent: bool
    reminder_24h_sent: bool
    reminder_1h_sent: bool
    odoo_event_id: Optional[int] = None
    outcome: Optional[str] = None
    outcome_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# NOTIFICATION SCHEMAS
# =============================================================================


class NotificationBase(BaseModel):
    channel: NotificationChannel
    to_address: str
    subject: Optional[str] = None  # For email
    body: str
    notification_type: NotificationType


class NotificationCreate(NotificationBase):
    tenant_id: UUID
    lead_id: Optional[UUID] = None
    appointment_id: Optional[UUID] = None
    call_id: Optional[UUID] = None
    from_address: Optional[str] = None
    template_id: Optional[str] = None
    template_data: Optional[dict[str, Any]] = None
    scheduled_for: Optional[datetime] = None
    priority: int = Field(default=0)


class Notification(NotificationBase):
    id: UUID
    tenant_id: UUID
    lead_id: Optional[UUID] = None
    appointment_id: Optional[UUID] = None
    direction: str
    from_address: Optional[str] = None
    status: NotificationStatus
    external_id: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    cost_usd: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# FOLLOW-UP TASK SCHEMAS
# =============================================================================


class FollowUpTaskBase(BaseModel):
    task_type: str  # call, email, whatsapp, sms, manual
    title: str
    description: Optional[str] = None
    scheduled_for: datetime


class FollowUpTaskCreate(FollowUpTaskBase):
    tenant_id: UUID
    lead_id: UUID
    sequence_id: Optional[str] = None
    sequence_name: Optional[str] = None
    sequence_step: Optional[int] = None
    is_ai_task: bool = True
    assigned_to: Optional[UUID] = None


class FollowUpTask(FollowUpTaskBase):
    id: UUID
    tenant_id: UUID
    lead_id: UUID
    sequence_id: Optional[str] = None
    sequence_step: Optional[int] = None
    status: str
    executed_at: Optional[datetime] = None
    result: dict[str, Any]
    is_ai_task: bool
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# HUMAN AGENT SCHEMAS
# =============================================================================


class HumanAgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["en"])
    priority: int = Field(default=0)


class HumanAgentCreate(HumanAgentBase):
    tenant_id: UUID
    max_concurrent_calls: int = Field(default=3)


class HumanAgent(HumanAgentBase):
    id: UUID
    tenant_id: UUID
    is_available: bool
    availability_status: str
    max_concurrent_calls: int
    current_call_count: int
    total_calls_handled: int
    avg_satisfaction_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# WEBHOOK PAYLOAD SCHEMAS (Twilio)
# =============================================================================


class TwilioVoiceWebhook(BaseModel):
    """Twilio voice webhook payload"""

    CallSid: str
    AccountSid: str
    From: str
    To: str
    CallStatus: str
    Direction: Optional[str] = None
    ForwardedFrom: Optional[str] = None
    CallerName: Optional[str] = None
    FromCity: Optional[str] = None
    FromState: Optional[str] = None
    FromZip: Optional[str] = None
    FromCountry: Optional[str] = None


class TwilioStatusWebhook(BaseModel):
    """Twilio call status webhook payload"""

    CallSid: str
    CallStatus: str
    CallDuration: Optional[int] = None
    RecordingUrl: Optional[str] = None
    RecordingSid: Optional[str] = None
    RecordingDuration: Optional[int] = None


class TwilioWhatsAppWebhook(BaseModel):
    """Twilio WhatsApp webhook payload"""

    MessageSid: str
    AccountSid: str
    From: str
    To: str
    Body: str
    NumMedia: int = 0
    MediaUrl0: Optional[str] = None
    ProfileName: Optional[str] = None


# =============================================================================
# API RESPONSE SCHEMAS
# =============================================================================


class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[list[str]] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class CallInitiateResponse(BaseModel):
    call_id: UUID
    twilio_call_sid: str
    status: str


class LeadScoreResponse(BaseModel):
    lead_id: UUID
    score: float
    temperature: LeadTemperature
    qualification_summary: str
    recommendations: list[str]
