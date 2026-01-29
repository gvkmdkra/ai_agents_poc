"""
Configuration management for the Calling Agent
Uses Pydantic Settings for environment variable management
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # OpenAI Configuration
    openai_api_key: str = Field(default=...)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # Ultravox Voice AI Configuration
    ultravox_api_key: str = Field(default=...)
    ultravox_api_endpoint: str = Field(default="https://api.ultravox.ai/api/calls")
    ultravox_voice_id: str = Field(default=...)
    ultravox_model_name: str = Field(default="fixie-ai/ultravox")
    ultravox_default_voice: str = Field(default="Mark")
    ultravox_temperature: float = Field(default=0.2)
    ultravox_tool_timeout: str = Field(default="15s")
    ultravox_http_timeout: float = Field(default=30.0)

    # Twilio Configuration
    twilio_account_sid: str = Field(default=...)
    twilio_auth_token: str = Field(default=...)
    twilio_phone_number: str = Field(default=...)

    # Pinecone Configuration
    pinecone_api_key: Optional[str] = Field(default=None)
    pinecone_environment: str = Field(default="us-east-1")
    pinecone_index_name: Optional[str] = Field(default=None)
    pinecone_metric: str = Field(default="cosine")

    # Turso Database Configuration
    turso_db_url: Optional[str] = Field(default=None)
    turso_db_auth_token: Optional[str] = Field(default=None)

    # Application Settings
    debug: bool = Field(default=True)
    log_level: str = Field(default="DEBUG")
    secret_key: str = Field(default="default-secret-key")
    environment: str = Field(default="development")

    # Server Configuration
    server_host: str = Field(default="0.0.0.0")
    server_port: int = Field(default=8000)
    api_base_url: str = Field(default="http://localhost:8000")

    # CORS Settings
    allowed_origins: str = Field(default="http://localhost:3000,http://localhost:8000")

    # Call Management
    call_records_file_path: str = Field(default="call_records.json")
    call_history_default_limit: int = Field(default=50)

    # RAG Configuration
    rag_top_k_results: int = Field(default=5)
    rag_similarity_threshold: float = Field(default=0.7)

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
