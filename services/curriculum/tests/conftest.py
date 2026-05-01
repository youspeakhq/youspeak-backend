import pytest
import os
import uuid
from httpx import ASGITransport, AsyncClient
from main import app
from config import settings

@pytest.fixture
def api_base() -> str:
    # Use the same prefix as the core proxy tests expect, 
    # but the curriculum app handles /curriculums directly.
    # However, for pure microservice tests, we hit the app's root.
    return ""

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        yield client

@pytest.fixture
def unique_suffix() -> str:
    return str(uuid.uuid4())[:8]

@pytest.fixture
def registered_school() -> dict:
    return {
        "headers": {"Authorization": "Bearer mock-admin-token"},
        "school_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4())
    }

@pytest.fixture
def teacher_headers() -> dict:
    return {"Authorization": "Bearer mock-teacher-token"}
