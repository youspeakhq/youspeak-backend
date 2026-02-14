"""Integration tests: References endpoints (public)."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_languages(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/references/languages")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    # Seeded languages: en, es, fr
    assert len(data) >= 1
    for lang in data:
        assert "id" in lang
        assert "name" in lang
        assert "code" in lang
