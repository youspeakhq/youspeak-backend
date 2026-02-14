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
