"""
Unified Database Models
SQLAlchemy models for multi-tenant Voice AI and Chat platform
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
import enum

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


def generate_short_id() -> str:
    """Generate a short ID for session identifiers"""
    return uuid.uuid4().hex[:12]


class CallStatus(enum.Enum):
    """Call status enumeration"""
    PENDING = "pending"
    INITIATING = "initiating"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallDirection(enum.Enum):
    """Call direction enumeration"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BROWSER = "browser"


class MessageRole(enum.Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class QueryMethod(enum.Enum):
    """Chat query method enumeration"""
    DATABASE = "database"
    RAG = "rag"
    DIRECT = "direct"
    LEAD_CAPTURE = "lead_capture"


# ============================================
# TENANT MODELS
# ============================================

class Tenant(Base):
    """Multi-tenant configuration"""
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Configuration
    system_prompt = Column(Text, nullable=True)
    welcome_message = Column(Text, default="Hello! How can I help you today?")
    voice = Column(String(50), default="lily")
    language = Column(String(10), default="en")

    # Pinecone Configuration
    pinecone_index_name = Column(String(255), nullable=True)
    pinecone_drive_index = Column(String(255), nullable=True)

    # Branding
    primary_color = Column(String(20), default="#4F46E5")
    logo_url = Column(String(500), nullable=True)

    # Feature Flags
    enable_voice_calling = Column(Boolean, default=True)
    enable_chat = Column(Boolean, default=True)
    enable_text_to_sql = Column(Boolean, default=True)
    enable_lead_capture = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("APIKey", back_populates="tenant", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tenant_active", "is_active"),
    )


class APIKey(Base):
    """API keys for tenant authentication"""
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Permissions
    can_call = Column(Boolean, default=True)
    can_chat = Column(Boolean, default=True)
    can_admin = Column(Boolean, default=False)

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")

    __table_args__ = (
        Index("idx_apikey_tenant", "tenant_id"),
        Index("idx_apikey_active", "is_active"),
    )


# ============================================
# CALL MODELS
# ============================================

class Call(Base):
    """Voice call records"""
    __tablename__ = "calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Call identifiers
    ultravox_call_id = Column(String(255), unique=True, nullable=True, index=True)
    twilio_call_sid = Column(String(64), unique=True, nullable=True, index=True)

    # Call details
    direction = Column(String(20), default="outbound")
    status = Column(String(30), default="pending", index=True)
    phone_number = Column(String(20), nullable=True)
    from_number = Column(String(20), nullable=True)

    # Client info
    client_name = Column(String(255), nullable=True)
    client_email = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Call content
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    recording_url = Column(String(500), nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Extra data
    extra_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="calls")

    __table_args__ = (
        Index("idx_call_tenant_status", "tenant_id", "status"),
        Index("idx_call_created", "created_at"),
        Index("idx_call_phone", "phone_number"),
    )


# ============================================
# CHAT MODELS
# ============================================

class Conversation(Base):
    """Chat conversation sessions"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Session identifier
    session_id = Column(String(36), unique=True, default=generate_short_id, index=True)

    # User info
    user_name = Column(String(255), default="Guest")
    user_email = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Conversation state
    is_active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)

    # Extra data
    extra_data = Column(JSON, nullable=True)
    source = Column(String(50), default="widget")  # widget, api, voice

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conv_tenant", "tenant_id"),
        Index("idx_conv_active", "is_active"),
        Index("idx_conv_created", "created_at"),
    )


class Message(Base):
    """Chat messages within conversations"""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Response metadata
    method = Column(String(20), nullable=True)  # database, rag, direct, lead_capture
    sources = Column(JSON, nullable=True)

    # Processing info
    tokens_used = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # Metadata
    message_metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_msg_conversation", "conversation_id"),
        Index("idx_msg_created", "created_at"),
    )


# ============================================
# LEAD MODELS
# ============================================

class Lead(Base):
    """Captured leads from chat and voice interactions"""
    __tablename__ = "leads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Lead details
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True)

    # Source tracking
    source = Column(String(50), default="chat")  # chat, voice, form
    session_id = Column(String(36), nullable=True, index=True)
    call_id = Column(String(36), nullable=True, index=True)

    # Lead status
    status = Column(String(30), default="new")  # new, contacted, qualified, converted, lost
    score = Column(Integer, nullable=True)

    # Additional info
    message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="leads")

    __table_args__ = (
        Index("idx_lead_tenant", "tenant_id"),
        Index("idx_lead_status", "status"),
        Index("idx_lead_created", "created_at"),
    )


# ============================================
# ANALYTICS MODELS
# ============================================

class AnalyticsEvent(Base):
    """Analytics events for tracking"""
    __tablename__ = "analytics_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_name = Column(String(100), nullable=False)
    event_data = Column(JSON, nullable=True)

    # Context
    session_id = Column(String(36), nullable=True)
    call_id = Column(String(36), nullable=True)
    user_id = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_analytics_tenant_type", "tenant_id", "event_type"),
    )
