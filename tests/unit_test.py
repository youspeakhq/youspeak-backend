"""Unit tests that do not require a running API or external services."""
import pytest
from app.config import settings


def test_settings_load():
    """Settings load from environment (e.g. CI env vars)."""
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.APP_NAME == "YouSpeak Backend"


def test_environment_flag():
    """Environment flags reflect ENVIRONMENT value."""
    # In CI we set ENVIRONMENT=test
    assert settings.ENVIRONMENT.lower() in ("development", "test", "production")
    assert settings.is_development == (settings.ENVIRONMENT.lower() == "development")
    assert settings.is_production == (settings.ENVIRONMENT.lower() == "production")
