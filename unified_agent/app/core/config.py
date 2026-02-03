"""
Unified AI Agent Configuration
Combines Voice Calling Agent and Chat Agent settings
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from functools import lru_cache
import os


class Settings(BaseSettings):
    """
    Unified configuration for the AI Agent Platform
    Supports both Voice Calling and Chat capabilities
    """

    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    app_name: str = Field(default="Unified AI Agent", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development/staging/production)")
    debug: bool = Field(default=False, description="Debug mode")

    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8000, description="Server port")
    api_base_url: str = Field(default="http://localhost:8000", description="API base URL for callbacks")

    # CORS Configuration
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000",
        description="Comma-separated allowed origins"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse allowed origins into list"""
        if self.allowed_origins:
            return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        return ["*"]

    # ============================================
    # AUTHENTICATION & SECURITY
    # ============================================
    secret_key: str = Field(default="", description="Secret key for JWT signing")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT token expiration in hours")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")

    # ============================================
    # DATABASE CONFIGURATION
    # ============================================
    # Primary Database (Turso/LibSQL)
    database_type: str = Field(default="turso", description="Database type: turso, sqlite, postgres")
    turso_database_url: str = Field(default="", description="Turso database URL")
    turso_auth_token: str = Field(default="", description="Turso authentication token")

    # SQLite fallback
    sqlite_database_path: str = Field(default="./data/unified_agent.db", description="SQLite database path")

    # PostgreSQL (optional)
    postgres_url: str = Field(default="", description="PostgreSQL connection URL")

    # MySQL (for customer data queries)
    mysql_host: str = Field(default="", description="MySQL host for customer data")
    mysql_port: int = Field(default=3306, description="MySQL port")
    mysql_user: str = Field(default="", description="MySQL user")
    mysql_password: str = Field(default="", description="MySQL password")
    mysql_database: str = Field(default="", description="MySQL database name")

    # SSH Tunnel for MySQL (optional)
    ssh_host: str = Field(default="", description="SSH tunnel host")
    ssh_port: int = Field(default=22, description="SSH tunnel port")
    ssh_user: str = Field(default="", description="SSH tunnel user")
    ssh_key_path: str = Field(default="", description="SSH private key path")

    # ============================================
    # AI/LLM CONFIGURATION
    # ============================================
    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="Default OpenAI model")
    openai_embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")

    # Ultravox (Voice AI)
    ultravox_api_key: str = Field(default="", description="Ultravox API key")
    ultravox_api_url: str = Field(default="https://api.ultravox.ai", description="Ultravox API URL")
    ultravox_voice: str = Field(default="lily", description="Default Ultravox voice")
    ultravox_model: str = Field(default="fixie-ai/ultravox-70B", description="Ultravox model")

    # ============================================
    # TELEPHONY CONFIGURATION (Twilio)
    # ============================================
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_phone_number: str = Field(default="", description="Twilio phone number")
    twilio_status_callback_url: str = Field(default="", description="Twilio status callback URL")

    # ============================================
    # VECTOR DATABASE (Pinecone)
    # ============================================
    pinecone_api_key: str = Field(default="", description="Pinecone API key")
    pinecone_environment: str = Field(default="", description="Pinecone environment")
    pinecone_index_name: str = Field(default="", description="Default Pinecone index")
    pinecone_top_k: int = Field(default=5, description="Default number of results for similarity search")

    # ============================================
    # CACHING (Redis)
    # ============================================
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_password: str = Field(default="", description="Redis password")
    cache_ttl_seconds: int = Field(default=3600, description="Default cache TTL")

    # ============================================
    # RATE LIMITING
    # ============================================
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=60, description="Requests per minute per tenant")
    rate_limit_calls_per_hour: int = Field(default=100, description="Calls per hour per tenant")
    rate_limit_max_concurrent_calls: int = Field(default=10, description="Max concurrent calls per tenant")

    # ============================================
    # WEBHOOK CONFIGURATION
    # ============================================
    webhook_timeout_seconds: int = Field(default=30, description="Webhook timeout")
    webhook_retry_attempts: int = Field(default=3, description="Number of retry attempts")
    webhook_signature_key: str = Field(default="", description="Webhook signature key")

    # ============================================
    # FEATURE FLAGS
    # ============================================
    enable_voice_calling: bool = Field(default=True, description="Enable voice calling features")
    enable_chat: bool = Field(default=True, description="Enable chat features")
    enable_text_to_sql: bool = Field(default=True, description="Enable Text-to-SQL features")
    enable_rag: bool = Field(default=True, description="Enable RAG document search")
    enable_lead_capture: bool = Field(default=True, description="Enable lead capture")
    enable_analytics: bool = Field(default=True, description="Enable analytics dashboard")

    # ============================================
    # LOGGING
    # ============================================
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")

    # ============================================
    # CELERY (Background Tasks)
    # ============================================
    celery_broker_url: str = Field(default="redis://localhost:6379/0", description="Celery broker URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", description="Celery result backend")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": False
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
