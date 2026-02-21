"""Shared pytest fixtures for E2E and integration tests."""

import os
import uuid
import pytest

# Load .env so DATABASE_URL, SECRET_KEY available for requires_db check
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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
        base = os.getenv("LIVE_SERVER_URL", f"http://localhost:8000")
        return f"{base}{settings.API_V1_PREFIX}"
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


@pytest.fixture
async def class_id_for_student(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a teacher, have them create a class, return class_id."""
    teacher_email = f"t_{unique_suffix}@test.com"
    # Admin invites teacher
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T", "last_name": "One", "email": teacher_email},
    )
    assert resp.status_code == 200
    code = resp.json()["data"]["access_code"]
    # Register teacher
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": teacher_email,
            "password": "Pass123!",
            "first_name": "T",
            "last_name": "One",
        },
    )
    # Login teacher
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_email, "password": "Pass123!"},
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Get semesters
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=headers)
    semesters = resp.json().get("data", [])
    if not semesters:
        # Create one if missing
        await async_client.post(
            f"{api_base}/classrooms", # Admin can create semesters/classrooms or just mock one
            headers=registered_school["headers"], # Actually fallback to registered_school to ensure semester exists or just assume it exists
            json={"name": f"Dummy_{unique_suffix}", "language_id": 1, "level": "a1"}
        )
        resp = await async_client.get(f"{api_base}/schools/semesters", headers=headers)
        semesters = resp.json().get("data", [])
        
    semester_id = semesters[0]["id"]
    # Create class
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=headers,
        json={
            "name": f"Test Class {unique_suffix}",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]
