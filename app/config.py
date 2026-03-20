"""Application Configuration"""

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "YouSpeak Backend"
    APP_VERSION: str = "1.0.5"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # Security & Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS (5173 = Vite default dev server)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"
    ALLOWED_METHODS: str = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
    ALLOWED_HEADERS: str = "*"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    # AI Settings (Bedrock; MD_JSON mode supports any model: Nova, Gemma, etc.)
    AWS_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "YouSpeak <onboarding@resend.dev>"
    FRONTEND_SIGNUP_URL: str = "https://app.youspeak.com/signup"
    FRONTEND_RESET_PASSWORD_URL: str = "https://app.youspeak.com/reset-password"

    # Storage (Cloudflare R2 – S3-compatible)
    STORAGE_PUBLIC_BASE_URL: str = "https://storage.youspeak.com"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "youspeak"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Curriculum microservice (internal)
    CURRICULUM_SERVICE_URL: str = ""
    CURRICULUM_INTERNAL_SECRET: str = ""

    model_config = SettingsConfigDict(
        version="1.0.5",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def parse_origins(cls, v: str) -> List[str]:
        """Parse comma-separated origins into a list"""
        return [origin.strip() for origin in v.split(",")]

    @field_validator("ALLOWED_METHODS")
    @classmethod
    def parse_methods(cls, v: str) -> List[str]:
        """Parse comma-separated methods into a list"""
        return [method.strip() for method in v.split(",")]

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"


# Global settings instance
settings = Settings()
