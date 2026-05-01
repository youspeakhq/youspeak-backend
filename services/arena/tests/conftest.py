import pytest
import os
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from services.arena.main import app
from services.arena.config import settings
from services.arena.models_local.base import Base
from services.arena.security import create_access_token

CORE_SERVICE_URL = os.environ.get("CORE_SERVICE_URL", "http://localhost:8000")
LIVE_SERVER_URL = os.environ.get("LIVE_SERVER_URL", "http://localhost:8002")
USE_LIVE_SERVER = os.environ.get("TEST_USE_LIVE_SERVER", "").lower() == "true"

FAKE_TEACHER_ID = "00000000-0000-0000-0000-000000000002"
FAKE_CLASS_ID = "00000000-0000-0000-0000-000000000001"

requires_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set"
)

_test_engine = None
_TestSessionLocal = None


def _get_test_session_factory():
    global _test_engine, _TestSessionLocal
    if _TestSessionLocal is None:
        db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        _test_engine = create_async_engine(db_url, poolclass=NullPool)
        _TestSessionLocal = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)
    return _TestSessionLocal


@pytest.fixture
async def db() -> AsyncSession:
    session_factory = _get_test_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.rollback()
        finally:
            await session.close()


@pytest.fixture
def api_base() -> str:
    """Base URL for core service arena endpoints (CRUD lives in core)."""
    if USE_LIVE_SERVER:
        return f"{CORE_SERVICE_URL}/api/v1"
    return "http://test/api/v1"


@pytest.fixture
def arena_api_base() -> str:
    """Base URL for arena microservice endpoints (WebSocket, audio)."""
    if USE_LIVE_SERVER:
        return f"{LIVE_SERVER_URL}{settings.API_V1_PREFIX}"
    return f"http://test{settings.API_V1_PREFIX}"


@pytest.fixture
async def async_client(api_base: str):
    """HTTP client for core service arena CRUD endpoints."""
    if USE_LIVE_SERVER:
        async with AsyncClient(base_url=api_base, timeout=30.0) as client:
            yield client
    else:
        # In unit test mode, route to core via ASGI is not available —
        # use live server for integration tests that need core endpoints.
        async with AsyncClient(base_url=api_base, timeout=30.0) as client:
            yield client


@pytest.fixture
async def arena_client(arena_api_base: str):
    """HTTP client for arena microservice endpoints."""
    if USE_LIVE_SERVER:
        async with AsyncClient(base_url=arena_api_base, timeout=30.0) as client:
            yield client
    else:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=arena_api_base, timeout=30.0) as client:
            yield client


@pytest.fixture
def unique_suffix() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


@pytest.fixture
def teacher_token() -> str:
    return create_access_token({"sub": FAKE_TEACHER_ID, "type": "access"})


@pytest.fixture
def teacher_headers(teacher_token: str) -> dict:
    return {"Authorization": f"Bearer {teacher_token}"}


FAKE_STUDENT_IDS = [
    f"00000000-0000-0000-0000-00000000001{i}" for i in range(5)
]


@pytest.fixture
def teacher_with_class_and_students(teacher_headers: dict) -> dict:
    """Fixed teacher + class + student IDs for tests that need class/student context."""
    return {
        "headers": teacher_headers,
        "class_id": FAKE_CLASS_ID,
        "student_ids": FAKE_STUDENT_IDS,
    }


@pytest.fixture
def registered_school() -> dict:
    admin_token = create_access_token({"sub": "00000000-0000-0000-0000-000000000001", "type": "access"})
    return {
        "headers": {"Authorization": f"Bearer {admin_token}"},
        "school_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "00000000-0000-0000-0000-000000000002",
    }


# Mocking Core API for Arena microservice tests
# autouse=False: only apply in unit-test mode. When USE_LIVE_SERVER=true, tests
# make real HTTP calls to localhost:8000 and respx must not intercept them.
@pytest.fixture(autouse=not USE_LIVE_SERVER)
def mock_core_api(respx_mock):
    """Mock Core API responses for Arena microservice tests (unit-test mode only)."""
    respx_mock.get(url__regex=r".*/internal/arenas/.*").mock(
        return_value=httpx.Response(200, json={
            "id": "00000000-0000-0000-0000-000000000001",
            "title": "Mock Arena",
            "status": "not_started",
            "language_code": "en",
            "participants": [
                {"user_id": "00000000-0000-0000-0000-000000000010", "role": "participant"},
                {"user_id": "00000000-0000-0000-0000-000000000011", "role": "participant"},
            ],
        })
    )

    respx_mock.get(url__regex=r".*/internal/verify-token.*").mock(
        return_value=httpx.Response(200, json={"user_id": "00000000-0000-0000-0000-000000000010"})
    )

    respx_mock.get(url__regex=r".*/internal/classes/.*").mock(
        return_value=httpx.Response(200, json={"id": "00000000-0000-0000-0000-000000000001", "name": "Mock Class"})
    )
