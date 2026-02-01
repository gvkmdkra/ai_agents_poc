"""
Database Models

These models represent the database schema and are used by all
database adapters (Turso, PostgreSQL, etc.)
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CallTranscriptDB(BaseModel):
    """Database model for call transcript entries"""
    id: Optional[int] = None
    call_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    speaker: str  # "agent" or "user"
    text: str
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class CallSummaryDB(BaseModel):
    """Database model for call summaries"""
    id: Optional[int] = None
    call_id: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None  # "positive", "neutral", "negative"
    action_items: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class CallRecordDB(BaseModel):
    """Database model for call records"""
    id: Optional[int] = None
    call_id: str
    status: str  # "pending", "ringing", "in_progress", "completed", "failed", etc.
    direction: str  # "inbound" or "outbound"
    phone_number: str
    from_number: str
    ultravox_call_id: Optional[str] = None
    twilio_call_sid: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting_message: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# SQL Schema definitions for different databases
TURSO_SCHEMA = """
-- Call Records Table
CREATE TABLE IF NOT EXISTS call_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    direction TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    from_number TEXT NOT NULL,
    ultravox_call_id TEXT,
    twilio_call_sid TEXT,
    system_prompt TEXT,
    greeting_message TEXT,
    metadata TEXT DEFAULT '{}',
    error_message TEXT,
    duration_seconds INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT
);

-- Call Transcripts Table
CREATE TABLE IF NOT EXISTS call_transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    speaker TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    FOREIGN KEY (call_id) REFERENCES call_records(call_id) ON DELETE CASCADE
);

-- Call Summaries Table
CREATE TABLE IF NOT EXISTS call_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT UNIQUE NOT NULL,
    summary TEXT NOT NULL,
    key_points TEXT DEFAULT '[]',
    sentiment TEXT,
    action_items TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (call_id) REFERENCES call_records(call_id) ON DELETE CASCADE
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_call_records_status ON call_records(status);
CREATE INDEX IF NOT EXISTS idx_call_records_created_at ON call_records(created_at);
CREATE INDEX IF NOT EXISTS idx_call_transcripts_call_id ON call_transcripts(call_id);
CREATE INDEX IF NOT EXISTS idx_call_summaries_call_id ON call_summaries(call_id);
"""

POSTGRES_SCHEMA = """
-- Call Records Table
CREATE TABLE IF NOT EXISTS call_records (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    direction VARCHAR(20) NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    from_number VARCHAR(50) NOT NULL,
    ultravox_call_id VARCHAR(255),
    twilio_call_sid VARCHAR(255),
    system_prompt TEXT,
    greeting_message TEXT,
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    duration_seconds INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

-- Call Transcripts Table
CREATE TABLE IF NOT EXISTS call_transcripts (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(255) NOT NULL REFERENCES call_records(call_id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    speaker VARCHAR(50) NOT NULL,
    text TEXT NOT NULL,
    confidence FLOAT
);

-- Call Summaries Table
CREATE TABLE IF NOT EXISTS call_summaries (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(255) UNIQUE NOT NULL REFERENCES call_records(call_id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    key_points JSONB DEFAULT '[]',
    sentiment VARCHAR(20),
    action_items JSONB DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_call_records_status ON call_records(status);
CREATE INDEX IF NOT EXISTS idx_call_records_created_at ON call_records(created_at);
CREATE INDEX IF NOT EXISTS idx_call_transcripts_call_id ON call_transcripts(call_id);
CREATE INDEX IF NOT EXISTS idx_call_summaries_call_id ON call_summaries(call_id);
"""
