import pytest
import os
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from services.arena.main import app
from services.arena.config import settings
from services.arena.models_local.base import Base

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
    return f"http://test{settings.API_V1_PREFIX}"

@pytest.fixture
async def async_client(api_base: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=api_base, timeout=30.0) as client:
        yield client

@pytest.fixture
def unique_suffix() -> str:
    import uuid
    return str(uuid.uuid4())[:8]

@pytest.fixture
def teacher_headers() -> dict:
    return {"Authorization": "Bearer mock-teacher-token"}

@pytest.fixture
def registered_school() -> dict:
    return {
        "headers": {"Authorization": "Bearer mock-admin-token"},
        "school_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "00000000-0000-0000-0000-000000000002"
    }

# Mocking Core API for Arena tests
@pytest.fixture(autouse=True)
def mock_core_api(respx_mock):
    """Mock Core API responses for Arena tests."""
    # Mock /internal/arenas/{id}
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

    # Mock /internal/verify-token
    respx_mock.get(url__regex=r".*/internal/verify-token.*").mock(
        return_value=httpx.Response(200, json={"user_id": "00000000-0000-0000-0000-000000000010"})
    )

    # Mock /internal/classes/{id}
    respx_mock.get(url__regex=r".*/internal/classes/.*").mock(
        return_value=httpx.Response(200, json={"id": "00000000-0000-0000-0000-000000000001", "name": "Mock Class"})
    )
