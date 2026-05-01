"""Arena Service Configuration"""

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for Arena service"""

    # Application
    APP_NAME: str = "YouSpeak Arena Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1/arenas/live"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # Database (Shared with core for Phase 1)
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Security & Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    INTERNAL_API_SECRET: str = "dev_internal_secret"

    # Redis (Shared for Pub/Sub and scaling)
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Settings (Bedrock)
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"

    # Azure Speech (Pronunciation Assessment)
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = "eastus"

    # Cloudflare RealtimeKit (Audio Conferencing)
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_REALTIMEKIT_APP_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""

    # Internal communication
    CORE_SERVICE_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"


settings = Settings()
