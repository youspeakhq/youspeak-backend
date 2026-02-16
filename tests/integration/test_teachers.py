"""Integration tests: Teachers endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_teachers(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_create_teacher_invite(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Admin creates teacher (is_active=False); code sent via email. Teacher activates with code."""
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "New",
            "last_name": "Teacher",
            "email": f"newteacher_{unique_suffix}@test.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_code" in data
    assert "teacher_id" in data


@pytest.mark.asyncio
async def test_create_teacher_with_classroom(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
    classroom_id,
):
    """Admin creates teacher and assigns to classroom."""
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "Classroom",
            "last_name": "Teacher",
            "email": f"ct_{unique_suffix}@test.com",
            "classroom_ids": [classroom_id],
        },
    )
    assert resp.status_code == 200
    teacher_id = resp.json()["data"]["teacher_id"]
    resp = await async_client.get(
        f"{api_base}/classrooms/{classroom_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["teacher_count"] >= 1


@pytest.fixture
async def classroom_id(async_client, api_base, registered_school, unique_suffix):
    """Create a classroom for teacher assignment test."""
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"Teacher Test Room {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]
