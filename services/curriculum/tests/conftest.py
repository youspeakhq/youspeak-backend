"""Pytest fixtures for curriculum service tests. Run with PYTHONPATH=services/curriculum from repo root."""

import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

# Ensure curriculum service is on path when running from repo root
_svc = os.path.join(os.path.dirname(__file__), "..")
if _svc not in os.sys.path:
    os.sys.path.insert(0, os.path.abspath(_svc))

from main import app


requires_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL required for curriculum service integration tests",
)


@pytest.fixture
def school_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def curriculum_headers(school_id: str) -> dict:
    return {"X-School-Id": school_id}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        timeout=30.0,
    ) as ac:
        yield ac


@pytest.fixture
async def existing_school_id():
    """Return one existing school_id from DB for create tests (FK). Skip if no schools."""
    from sqlalchemy import text
    from database import engine
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT id FROM schools LIMIT 1"))
        row = r.fetchone()
    if row is None:
        pytest.skip("No school in DB; run core migrations or integration tests first")
    return str(row[0])
