"""Shared pytest fixtures for E2E and integration tests."""

import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings

# Skip integration/E2E tests if DATABASE_URL or SECRET_KEY not set
requires_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not os.getenv("SECRET_KEY"),
    reason="DATABASE_URL and SECRET_KEY must be set",
)


def _get_api_base() -> str:
    """API base URL. In CI (TEST_USE_LIVE_SERVER=true), hit running server to avoid async teardown issues."""
    if os.getenv("TEST_USE_LIVE_SERVER", "").lower() == "true":
        return f"http://localhost:8000{settings.API_V1_PREFIX}"
    return f"http://test{settings.API_V1_PREFIX}"


@pytest.fixture
def api_base() -> str:
    """Base URL for API requests."""
    return _get_api_base()


@pytest.fixture
async def async_client(api_base: str):
    """Async HTTP client. Uses live server in CI to avoid RuntimeError: Task pending during teardown."""
    use_live = os.getenv("TEST_USE_LIVE_SERVER", "").lower() == "true"
    if use_live:
        client = AsyncClient(base_url=api_base, timeout=30.0)
    else:
        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url=api_base, timeout=30.0)
    yield client
    await client.aclose()


@pytest.fixture
def unique_suffix() -> str:
    """Unique suffix for test data to avoid collisions."""
    return str(uuid.uuid4())[:8]


@pytest.fixture
async def registered_school(async_client: AsyncClient, api_base: str, unique_suffix: str):
    """
    Register a school and return (admin_email, password, school_id, headers).
    """
    admin_email = f"admin_{unique_suffix}@test.example.com"
    password = "TestPassword123!"
    school_name = f"Test School {unique_suffix}"

    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": admin_email,
            "password": password,
            "school_name": school_name,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    school_id = data["data"]["school_id"]

    # Login to get token
    login_resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": admin_email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "admin_email": admin_email,
        "password": password,
        "school_id": school_id,
        "school_name": school_name,
        "headers": headers,
    }
