"""Integration tests: Admin endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_admin_stats(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/admin/stats",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "active_classes" in data
    assert "total_students" in data
    assert "total_teachers" in data


@pytest.mark.asyncio
async def test_get_activity_log(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/admin/activity",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert "data" in resp.json()


@pytest.mark.asyncio
async def test_get_leaderboard(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/admin/leaderboard",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "top_classes" in data
    assert "top_students" in data
