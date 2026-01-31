"""
Voice Agent Configuration

Environment-based configuration for all integrations and services.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class TwilioSettings:
    """Twilio API configuration"""

    account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))

    # Webhook URLs (set based on deployment)
    webhook_base_url: str = field(
        default_factory=lambda: os.getenv("VOICE_AGENT_WEBHOOK_URL", "https://api.example.com")
    )

    @property
    def voice_answer_url(self) -> str:
        return f"{self.webhook_base_url}/voice/webhook/voice/answer"

    @property
    def voice_status_url(self) -> str:
        return f"{self.webhook_base_url}/voice/webhook/voice/status"

    @property
    def voice_fallback_url(self) -> str:
        return f"{self.webhook_base_url}/voice/webhook/voice/fallback"

    @property
    def media_stream_url(self) -> str:
        # WebSocket URL for Media Streams
        ws_url = self.webhook_base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_url}/voice/media-stream"

    @property
    def whatsapp_webhook_url(self) -> str:
        return f"{self.webhook_base_url}/voice/webhook/whatsapp/incoming"

    @property
    def sms_webhook_url(self) -> str:
        return f"{self.webhook_base_url}/voice/webhook/sms/incoming"

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)


@dataclass
class UltravoxSettings:
    """Ultravox API configuration"""

    api_key: str = field(default_factory=lambda: os.getenv("ULTRAVOX_API_KEY", ""))
    api_url: str = field(
        default_factory=lambda: os.getenv("ULTRAVOX_API_URL", "wss://api.ultravox.ai/v1/realtime")
    )
    http_url: str = field(
        default_factory=lambda: os.getenv("ULTRAVOX_HTTP_URL", "https://api.ultravox.ai/v1")
    )
    model: str = field(
        default_factory=lambda: os.getenv("ULTRAVOX_MODEL", "fixie-ai/ultravox-v0.4")
    )

    # Voice defaults
    default_voice_provider: str = "elevenlabs"
    default_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    )
    default_language: str = "en-US"

    # ASR settings
    asr_provider: str = "deepgram"
    asr_model: str = "nova-2"

    # Turn detection
    turn_detection_threshold: float = 0.5
    silence_duration_ms: int = 500

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class OpenAISettings:
    """OpenAI API configuration"""

    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    conversation_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    )
    classification_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_CLASSIFICATION_MODEL", "gpt-4o-mini")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    temperature: float = 0.7
    max_tokens: int = 4096

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class OdooSettings:
    """Odoo CRM configuration"""

    url: str = field(default_factory=lambda: os.getenv("ODOO_URL", ""))
    database: str = field(default_factory=lambda: os.getenv("ODOO_DATABASE", ""))
    api_key: str = field(default_factory=lambda: os.getenv("ODOO_API_KEY", ""))
    company_id: int = field(
        default_factory=lambda: int(os.getenv("ODOO_COMPANY_ID", "1"))
    )
    default_sales_team_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("ODOO_SALES_TEAM_ID")) if os.getenv("ODOO_SALES_TEAM_ID") else None
    )
    default_salesperson_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("ODOO_SALESPERSON_ID")) if os.getenv("ODOO_SALESPERSON_ID") else None
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.database and self.api_key)


@dataclass
class SendGridSettings:
    """SendGrid email configuration"""

    api_key: str = field(default_factory=lambda: os.getenv("SENDGRID_API_KEY", ""))
    from_email: str = field(
        default_factory=lambda: os.getenv("SENDGRID_FROM_EMAIL", "noreply@example.com")
    )
    from_name: str = field(
        default_factory=lambda: os.getenv("SENDGRID_FROM_NAME", "AI Voice Agent")
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class DatabaseSettings:
    """Database configuration"""

    url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://user:password@localhost:5432/voiceagent"
        )
    )
    pool_size: int = field(
        default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10"))
    )
    max_overflow: int = field(
        default_factory=lambda: int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    )


@dataclass
class RedisSettings:
    """Redis configuration"""

    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    password: Optional[str] = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD")
    )
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class VoiceAgentSettings:
    """Main configuration container"""

    # Environment
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    # Service integrations
    twilio: TwilioSettings = field(default_factory=TwilioSettings)
    ultravox: UltravoxSettings = field(default_factory=UltravoxSettings)
    openai: OpenAISettings = field(default_factory=OpenAISettings)
    odoo: OdooSettings = field(default_factory=OdooSettings)
    sendgrid: SendGridSettings = field(default_factory=SendGridSettings)

    # Infrastructure
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)

    # Voice Agent defaults
    default_language: str = "en-US"
    default_timezone: str = "UTC"
    max_conversation_turns: int = 50
    call_recording_enabled: bool = True
    transcription_enabled: bool = True

    # Lead scoring thresholds
    hot_lead_threshold: float = 0.75
    warm_lead_threshold: float = 0.45

    # Escalation settings
    escalation_sentiment_threshold: float = -0.5
    max_ai_attempts_before_escalation: int = 3

    # Rate limiting
    max_concurrent_calls_per_tenant: int = 50
    max_outbound_calls_per_hour: int = 100

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> list[str]:
        """Validate configuration and return list of missing items"""
        missing = []

        if not self.twilio.is_configured:
            missing.append("Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)")

        if not self.ultravox.is_configured:
            missing.append("Ultravox API key (ULTRAVOX_API_KEY)")

        if not self.openai.is_configured:
            missing.append("OpenAI API key (OPENAI_API_KEY)")

        # Odoo and SendGrid are optional
        return missing


# Global settings instance
settings = VoiceAgentSettings()


def get_settings() -> VoiceAgentSettings:
    """Get the global settings instance"""
    return settings


# Environment variable template for reference
ENV_TEMPLATE = """
# =============================================================================
# VOICE AGENT ENVIRONMENT CONFIGURATION
# =============================================================================

# Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# =============================================================================
# TWILIO CONFIGURATION
# =============================================================================
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
VOICE_AGENT_WEBHOOK_URL=https://your-domain.com

# =============================================================================
# ULTRAVOX CONFIGURATION
# =============================================================================
ULTRAVOX_API_KEY=your_ultravox_api_key
ULTRAVOX_API_URL=wss://api.ultravox.ai/v1/realtime
ULTRAVOX_MODEL=fixie-ai/ultravox-v0.4

# ElevenLabs voice (used by Ultravox)
ELEVENLABS_DEFAULT_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# =============================================================================
# OPENAI CONFIGURATION
# =============================================================================
OPENAI_API_KEY=your_openai_api_key
OPENAI_CONVERSATION_MODEL=gpt-4o
OPENAI_CLASSIFICATION_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# =============================================================================
# ODOO CRM CONFIGURATION (Optional)
# =============================================================================
ODOO_URL=https://your-company.odoo.com
ODOO_DATABASE=your_database
ODOO_API_KEY=your_odoo_api_key
ODOO_COMPANY_ID=1
ODOO_SALES_TEAM_ID=1
ODOO_SALESPERSON_ID=1

# =============================================================================
# SENDGRID EMAIL (Optional)
# =============================================================================
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=noreply@example.com
SENDGRID_FROM_NAME=AI Voice Agent

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL=postgresql://user:password@localhost:5432/voiceagent
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# =============================================================================
# REDIS
# =============================================================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
"""
