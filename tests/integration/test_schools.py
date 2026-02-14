"""Integration tests: Schools endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_school_profile_requires_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/schools/profile")
    assert resp.status_code == 403  # No Bearer token


@pytest.mark.asyncio
async def test_get_school_profile_success(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == registered_school["school_name"]


@pytest.mark.asyncio
async def test_update_school_profile(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    resp = await async_client.put(
        f"{api_base}/schools/profile",
        headers=registered_school["headers"],
        json={
            "address_country": "Canada",
            "address_state": "ON",
            "address_city": "Toronto",
            "address_zip": "M5V 1A1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["address_country"] == "Canada"
    assert data["address_city"] == "Toronto"


@pytest.mark.asyncio
async def test_update_school_programs(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.put(
        f"{api_base}/schools/program",
        headers=registered_school["headers"],
        json={"languages": ["es", "fr"]},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_semesters(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/schools/semesters",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
