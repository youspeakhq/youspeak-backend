"""Health endpoint behavior: returns 200 and expected shape."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert "service" in data


@pytest.mark.asyncio
async def test_health_ready_returns_ok_or_503(client: AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    if resp.status_code == 200:
        assert data.get("database") == "connected"
