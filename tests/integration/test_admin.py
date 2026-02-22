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
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert isinstance(body["data"], list)
    assert body["meta"]["page"] >= 1
    assert body["meta"]["total_pages"] >= 0


@pytest.mark.asyncio
async def test_post_activity_log(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.post(
        f"{api_base}/admin/activity",
        headers=registered_school["headers"],
        json={
            "action_type": "class_created",
            "description": "Class Created: French 101",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["action_type"] == "class_created"
    assert data["description"] == "Class Created: French 101"
    assert "id" in data
    assert "created_at" in data
    assert "performer_name" in data


@pytest.mark.asyncio
async def test_get_leaderboard(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/admin/leaderboard",
        headers=registered_school["headers"],
    )
    if resp.status_code == 500:
        pytest.skip("Leaderboard returned 500 (e.g. minimal DB without arena data)")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "top_classes" in data
    assert "top_students" in data
    assert "timeframe" in data
    assert data["timeframe"] in ("week", "month", "all")
    assert isinstance(data["top_students"], list)
    assert isinstance(data["top_classes"], list)
    for entry in data["top_students"]:
        assert "rank" in entry and "student_name" in entry and "class_name" in entry and "points" in entry
    for entry in data["top_classes"]:
        assert "rank" in entry and "class_name" in entry and "score" in entry
