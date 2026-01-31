"""
Tenant Configuration Models
Supports multi-tenant deployment for different clients
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class TenantVoiceConfig(BaseModel):
    """Voice configuration for a tenant"""
    voice_id: Optional[str] = None
    voice_name: str = "Mark"
    language: str = "en-US"
    speaking_rate: float = 1.0
    pitch: float = 1.0


class TenantPromptConfig(BaseModel):
    """Prompt configuration for a tenant"""
    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="Default system prompt for the tenant"
    )
    greeting_template: str = Field(
        default="Hello! This is {agent_name} from {company_name}. How can I help you today?",
        description="Greeting template with placeholders"
    )
    farewell_template: str = Field(
        default="Thank you for calling {company_name}. Have a great day!",
        description="Farewell template"
    )
    fallback_response: str = Field(
        default="I'm sorry, I didn't understand that. Could you please repeat?",
        description="Fallback response when AI fails"
    )


class TenantCallConfig(BaseModel):
    """Call configuration for a tenant"""
    max_duration_seconds: int = 600
    max_retries: int = 3
    retry_delay_seconds: int = 60
    record_calls: bool = False
    transcription_enabled: bool = True
    summary_enabled: bool = True
    allowed_hours_start: int = 9  # 9 AM
    allowed_hours_end: int = 21   # 9 PM
    timezone: str = "UTC"


class TenantWebhookConfig(BaseModel):
    """Webhook configuration for a tenant"""
    call_started_url: Optional[str] = None
    call_ended_url: Optional[str] = None
    transcript_url: Optional[str] = None
    summary_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class TenantConfig(BaseModel):
    """Complete tenant configuration"""
    tenant_id: str = Field(..., description="Unique tenant identifier")
    tenant_name: str = Field(..., description="Display name for the tenant")
    company_name: str = Field(..., description="Company name for prompts")
    agent_name: str = Field(default="AI Assistant", description="Agent name for prompts")

    # API Keys (can override global)
    twilio_phone_number: Optional[str] = None
    ultravox_voice_id: Optional[str] = None

    # Sub-configurations
    voice: TenantVoiceConfig = Field(default_factory=TenantVoiceConfig)
    prompts: TenantPromptConfig = Field(default_factory=TenantPromptConfig)
    calls: TenantCallConfig = Field(default_factory=TenantCallConfig)
    webhooks: TenantWebhookConfig = Field(default_factory=TenantWebhookConfig)

    # Metadata
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_greeting(self) -> str:
        """Get formatted greeting message"""
        return self.prompts.greeting_template.format(
            agent_name=self.agent_name,
            company_name=self.company_name
        )

    def get_farewell(self) -> str:
        """Get formatted farewell message"""
        return self.prompts.farewell_template.format(
            agent_name=self.agent_name,
            company_name=self.company_name
        )

    def get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get system prompt with optional context"""
        prompt = self.prompts.system_prompt

        # Add tenant context
        prompt += f"\n\nYou are {self.agent_name} representing {self.company_name}."

        if context:
            prompt += f"\n\nAdditional context: {context}"

        return prompt


class TenantAPIKey(BaseModel):
    """API Key for tenant authentication"""
    api_key: str
    tenant_id: str
    name: str
    is_active: bool = True
    permissions: List[str] = Field(default_factory=lambda: ["calls:read", "calls:write"])
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
